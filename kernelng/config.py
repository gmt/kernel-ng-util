#!/usr/bin/env python
#-*- coding:utf-8 -*-
# vim:ai:sta:et:ts=4:sw=4:sts=4

"""kernelng 0.x
 Tool for maintaining customized overlays of kernel-ng.eclass-based ebuilds

Copyright 2005-2014 Gentoo Foundation

        Copyright (C) 2014 Gregory M. Turner <gmt@be-evil.net>

Distributed under the terms of the GNU General Public License v2
 This program is free software; you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, version 2 of the License.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program; if not, write to the Free Software
 Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA.

"""

import os
import sys
import re

from collections import OrderedDict
from itertools import chain

import click
from click._compat import iteritems

from .output import has_verbose_level, echov, sechov

try:
    from portage.data import portage_uid as _portage_uid, portage_gid as _portage_gid
except ImportError:
    _portage_gid = 250
    _portage_uid = 250

# python3 wigs out if these are proxies
portage_uid = int(_portage_uid)
portage_gid = int(_portage_gid)

# eprefixifiable dummy value
EPREFIX = "@GENTOO_PORTAGE_EPREFIX@"

# non-eprefixified fallback behavior: ask portage or assume empty
if EPREFIX == "@GENTOO_%s_EPREFIX@" % "PORTAGE":
    try:
        from portage.const import EPREFIX as _EPREFIX
    except ImportError:
        _EPREFIX = ''
    EPREFIX = _EPREFIX

PROGNAME = sys.argv[0].split(os.path.sep)[-1] if len(sys.argv) >= 1 else 'kernelng'
PROGDESC = 'kernel-ng-util'
FRAMEWORK = 'kernel-ng'

PORTAGE_CONF_DIR = '/etc/portage'
REPOS_CONF = 'repos.conf'

REPOS_CONF_FILE = ''.join((
    EPREFIX,
    PORTAGE_CONF_DIR,
    os.path.sep,
    REPOS_CONF
))

KERNELNG_CONF = '%s.conf' % FRAMEWORK
KERNELNG_CONF_DIR = '/etc/%s' % FRAMEWORK

KERNELNG_CONF_FILE = ''.join((
    EPREFIX,
    KERNELNG_CONF_DIR,
    os.path.sep,
    KERNELNG_CONF
))

CONST_RE = re.compile('%\([^)]*\)[^\W\d_]', re.UNICODE)
SUBCONSTS = {
    'prog': PROGNAME,
    'progdesc': PROGDESC,
    'framework': FRAMEWORK,
    'eprefix': EPREFIX,
}

def subconsts(text, subconsts=SUBCONSTS):
    """Utility function to make substitutions from a dictionary of constants."""
    try:
        return text % subconsts if re.search(CONST_RE, text) else text
    except ValueError:
        if has_verbose_level(1):
           print('subconsts: error substituting for "%s".', file=sys.stderr)
        raise

class KNGConfigItemUnknownReason(Exception):
    def __init__(self, key, value, reason):
        super(KNGConfigItemUnknownReason, self).__init__(
            'Unknown KNGConfigItem reason "%s", assigning "%s" to "%s"' % (
                reason, value, key))

VALID_KNGCONFIGITEMREASONS=['stored', 'default', 'override']
def ValidateKNGConfigItemReason(key, value, reason):
    if reason not in VALID_KNGCONFIGITEMREASONS:
        raise KNGConfigItemUnknownReason(key, value, reason)

class KNGConfigItem(object):
    def __init__(self, key, value='__comment__', default=None, reason='default'):
        '''
        This constructor has two forms: KNGConfigItem(<comment-str>) and
        KNGConfigItem(<key>, <value>).  default and reason apply only to the second
        form -- for comments, the default is always None and the reason is always 'stored'
        '''
        ValidateKNGConfigItemReason(key, value, reason)
        if value == '__comment__':
            key, value = value, key
            default=None
            reason='stored'
        self._key = key
        self._value = value
        self._reason = reason
        if reason == 'default' and default is None:
            self._default = value
        elif reason == 'default' and default is not None and value != default:
            raise KNGConfigItemUnknownReason(key, value, 'bad_default')
        else:
            self._default = default

    @property
    def key(self):
        return self._key
    @property
    def value(self):
        return self._value
    @property
    def default(self):
        return self._default
    @property
    def reason(self):
        return self._reason
    @property
    def isexplicit(self):
        if self.reason == 'default':
            return False
        elif self.reason == 'override':
            # ?
            return False
        else:
            return True
    @property
    def iscomment(self):
        return (self.key == '__comment__')
    @property
    def comment(self):
        return self.value

    def setvalue(self, value, reason=None):
        if reason is not None:
            ValidateKNGConfigItemReason(self._key, value, reason)
            if reason == 'default' and self.default is not None:
                raise KNGConfigItemUnknownReason(key, value, 'bad_default')
            self._reason = reason
        else:
            if self.default and value == default:
                self._reason = 'default'
            else:
                self._reason = 'stored'
        self._value = value

    def __eq__(self, other):
        if isinstance(other, KNGConfigItem):
            if other.key != self.key:
                return False
            if other.value != self.value:
                return False
            if other.reason != self.reason:
                return False
            return True
        else:
            # fuck it
            return NotImplemented
    def __ne__(self, other):
        return not (self == other)
    def __gt__(self, other):
        if isinstance(other, KNGConfigItem):
            return self.key > other.key or (self.key == other.key and self.value > other.value) \
                or (self.key == other.key and self.value == other.value and self.reason > other.reason)
        else:
            return NotImplemented
    def __le__(self, other):
        return not self.__gt__(other)
    def __lt__(self, other):
        return (not self.__eq__(other)) and self.__le__(other)
    def __ge__(self, other):
        return self.__eq__(other) or self.__gt__(other)

kng_example_config_data = None
def KNGExampleConfigData():
    global kng_example_config_data

    if kng_example_config_data:
        return kng_example_config_data.copy()

    result = OrderedDict()

    result['implicit_global'] = (
        '# %(framework)s.conf',
        '',
        '# This file can be modified to match your system\'s needs.',
        '# The file has an "ini" type syntax of "<name> = <value>" pairs',
        '# preceeded by section headings enclosed with brackets like,',
        '# i.e.: "[section]".  Each section title corresponds to a portage',
        '# package atom, i.e.: [=sys-kernel/gentoo-sources-3.15*].',
        '#',
        '# Lines beginning with a "#" are treated as comments.  Empty lines',
        '# are ignored.  Quotation marks are not needed and will not be',
        '# preserved by the %(prog)s utility -- their use is discouraged.',
        '#',
        '#',
        '# A "[global]" section is also supported.  Any "<name> = <value>"',
        '# pairs appearing before any section header are considered',
        '# implicitly to be in the global section, so the "[global]" header',
        '# may be omitted, so long as all global settings come first.',
        '',
        '# overlay',
        '# -------',
        '# default value: site-%(framework)s',
        '# scope: global only',
        '#',
        '# Name of the site-wide %(framework)s portage overlay.',
        '# The overlay need not exist to be named here.  If it does',
        '# not exist it will be created automatically as required or',
        '# when the "%(prog)s overlay create" command is executed.',
        '',
        ( 'overlay', 'site-%(framework)s', True ),
        '',
        '# nameprefix',
        '# ==========',
        '# default value: %(prog)s_',
        '# scope: any',
        '#',
        '# Prefix applied to package names in the overlay.  For example,',
        '# if nameprefix is "foo", then the ebuild corresponding to',
        '# sys-kernel/gentoo-sources-3.16.3 in the overlay would be',
        '# sys-kernel/foogentoo-sources-3.16.3.  Making this empty',
        '# would result in identically named packages and is strongly',
        '# discouraged, although not technocratically prohibited.',
        '',
        ( 'nameprefix', '%(prog)s_' ),
        '',
        '# repos_conf',
        '# ==========',
        '# default value: %(eprefix)s/etc/portage/repos.conf',

        '# scope: global only',
        '#',
        '# Location of portage\'s repos.conf file.  If set to /dev/null,',
        '# %(framework)swill not automatically maintain the repos.conf file;',
        '# otherwise, when the overlay is created, this file will be',
        '# automatically modified to activate the %(framework)s overlay in',
        '# the portage package system.',
        '',
        ( 'repos_conf', '%(eprefix)s/etc/portage/repos.conf' ),
        '',
    )
    result['sys-kernel/gentoo-sources'] = (
        '# TODO',
        '# later',
        '',
    )

    for key in result.keys():
        val = result[key]
        result[key] = tuple(
            tuple(
                valsubitem if isinstance(valsubitem, bool) else subconsts(valsubitem)
                for valsubitem in valitem
            ) if isinstance(valitem, tuple) else subconsts(valitem)
            for valitem in val
        )
    kng_example_config_data = result.copy()
    return result

kng_global_defaults = None
def KNGGlobalDefaults():
    if kng_global_defaults:
        return kng_global_defaults.copy()
    ecd = KNGExampleConfigData()
    implicit = ecd['implicit_global'] if ecd.has_key('implicit_global') else ()
    explicit = ecd['global'] if ecd.has_key('global') else ()
    result = {
        valitem[0]: valitem[1]
        for valitem in chain(implicitKNGGlobalDefaults, explicitKNGGlobalDefaults)
        if isinstance(valitem, tuple)
    }
    kng_global_defaults = result.copy()
    return result

class KNGConfigItems(list):
    '''
    Implements a list of KNGConfigItem instances with some dict-like interfaces
    for, i.e., determining whether a particular configuration key is already in
    the list, or setting the key in-place via __getitem__.  For dict-like behaviors,
    the comments are ignored.
    '''
    def __contains__(self, key):
        if key == '__comment__':
            for item in self:
                if item.iscomment:
                    return True
            return False
        elif instanceof(key, KNGConfigItem):
            for item in self:
                if item == key:
                    return True
            return False
        else:
            for item in self:
                if item.iscomment and item.comment == key:
                    return True
                elif item.iscomment:
                    continue
                if item.key == key:
                    return True
            return False
    def iterkeypairs(self):
        return ( (item.key, item.value) for item in self if not item.iscomment )
    def iterkeys(self):
        return ( item[0] for item in self.iterkeypairs() )
    def itervalues(self):
        return ( item[1] for item in self.iterkeypairs() )
    def iterstored(self):
        return ( item for item in self if item.reason == 'stored' )
    def __getitem__(self, index):
        if isinstance(index, slice) or isinstance(index, int):
            return super(KNGConfigItems, self).__getitem__(index)
        for item in self:
            if (not item.iscomment) and item.key == index:
                return item
        raise KeyError(index)
    def __setitem__(self, index, value):
        if isinstance(index, slice) or isinstance(index, int):
            super(KNGConfigItems, self).__setitem__(index, value)
            return
        for itemindex, item in enumerate(self):
            if (not item.iscomment) and item.key == index:
                if isinstance(value, KNGConfigItem):
                    self[itemindex] = value
                    return
                else:
                    item.value = value
                    return
        if isinstance(value, KNGConfigItem):
            self.append(value)
        else:
            self.append(KNGConfigItem(index, value))
    def __delitem__(self, index):
        if isinstance(index, slice) or isinstance(index, int):
            super(KNGConfigItems, self).__delitem__(index)
        else:
            for itemindex, item in enumerate(self):
                if (not item.iscomment) and item.key == index:
                    super(KNGConfigItems, self).__delitem__(itemindex)
                    return
            raise IndexError('Could not find item matching index "%s" in %s to delete' % (index, self))
    def insert(self, index, value):
        if isinstance(index, int):
            super(KNGConfigItems, self).insert(index, value)
        else:
            for itemindex, item in enumerate(self):
                if (not item.iscomment) and item.key == index:
                    super(KNGConfigItems, self).insert(itemindex, value)
                    return
            raise IndexError('Could not find item matching insertion index "%s" in %s' % (index, self))
    def append(self, value):
        for itemindex, item in enumerate(self):
            if (not item.iscomment) and item.key == value.key:
                del(self[itemindex])
        super(KNGConfigItems, self).append(value)
    def extend(self, values):
        for v in values:
            self.append(v)
    def pop(self, index=-1):
        v = self[index]
        del self[index]
        return v
    def remove(self, value):
        for itemindex, item in enumerate(self):
            if item == value:
                del self[itemindex]
                return
        raise ValueError('%s not in list' % value)
    def __iadd__(self, values):
        self.extend(values)
        return self

class KNGConfig(OrderedDict):
    def __init__(self, kernelng_conf_file=KERNELNG_CONF_FILE, repos_conf_file=REPOS_CONF_FILE):
        self._kernelng_conf_file = kernelng_conf_file
        self._repos_conf_file = repos_conf_file
        super(KNGConfig, self).__init__()

    def loadExampleConfig(self):
        self.clear()
        ecd = KNGExampleConfigData()
        for key in ecd.keys():
            self[key] = KNGConfigItems()
            val = ecd[key]
            for item in val:
                if isinstance(item, tuple):
                    if len(item) > 2 and item[2] == True:
                        self[key].append(KNGConfigItem(item[0], item[1], reason='stored'))
                    else:
                        self[key].append(KNGConfigItem(item[0], item[1], default=item[1], reason='default'))
                else:
                    self[key].append(KNGConfigItem(item))

    def writeConfigText(self, file=None):
        '''
        Write the currently loaded configuration to a given file.

        :param file: If provided, the output will be written into the provided click.File object.
                     If not provided, output will go to standard output.
        '''
        keys = self.keys()
        for key in keys:
            if key != 'implicit_global':
                click.echo('[%s]' % key, file=file)
            vlist = self[key]
            if vlist:
                for item in vlist:
                    if item.iscomment:
                        click.echo(item.comment)
                    elif item.isexplicit:
                       click.echo('%(itemkey)s = %(itemvalue)s' % { 'itemkey': item.key, 'itemvalue': item.value }, file=file)

    def section(self, name):
        """
        Returns the named section if it exists, or, if not, creates an empty KNGConfigItems
        instance, attaches it to this KNGConfig as the 'name' section, and returns it.
        """
        if name in self:
            return self['name']
        else:
            v = KNGConfigItems()
            self['name'] = v
            return v
