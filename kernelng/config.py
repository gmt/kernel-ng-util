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
from itertools import chain, islice, count, repeat

import click
from click._compat import iteritems

from .output import has_verbose_level, echov, sechov
import portage

try:
    portage.proxy.lazyimport.lazyimport(globals(),
        'portage.data:portage_uid,portage_gid')
except ImportError:
    portage_uid = 250
    portage_gid = 250

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
EKERNELNG_CONF_DIR = '%s%s' % (EPREFIX, KERNELNG_CONF_DIR)

KERNELNG_CONF_FILE = ''.join((
    EKERNELNG_CONF_DIR,
    os.path.sep,
    KERNELNG_CONF,
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
    except ValueError as e:
        echov('subconsts: error substituting: "%s".' % str(e), err=True)
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

# KNGConfigItem, KNGConfigItems, KNGConfig, and fetal-ness/daddy
# ==============================================================
# The interface here is tolerable but the plumbing is ugly and inelegant
# due to code evolution by incremental hacking.  The whole thing should probably be
# scrapped and re-coded from scratch, truth be told, now that I've figued out
# what it is I'm trying to accomplish.
#
# The basic data-structure we are building could be thought of as a dict of {<str>: <list>}
# items; the lists could be thought of as containing (<str>, <str>) tuples.  In fact,
# that's an oversimplification.  The dict is actually a KNGConfig, which is an OrderedDict
# subclass that logically represents the entire contents of a kernel-ng.conf file, with
# each dictionary key representing a section.  The list is actually a KNGConfigItems instance
# and the list-items are KNGConfigItem instances (the analogue of the (<str>, <str>) tuples).
# Each KNGConfigItem either represents a configuration-file comment or a standard configuration-file
# line-item (i.e.: key=value).
#
# We use the OrderedDict so that we can round-trip the configuration file without re-ordering
# the sections.  Initially this will be fairly broken, but the enhancements to achieve full
# .conf => OO => .conf round-trip capabilities are simply to saving off some formatting metadata
# at the KNGConfigItem level during "deserialization" -- aka parsing, what-have-you.  First,
# .conf-file deserialization of /any/ sort will need to be implemented :S.
#
# The motivation for much of the crazyness below is that I wanted consumers to be able to say:
# "kngconfig['foo']['bar'] = 'baz'", and have the bar setting in the foo section recieve a value of
# 'baz'.  Even so, thereafter, kngconfig['foo']['bar'] would not be 'baz', but a KNGConfigItem
# with value 'baz' and key 'bar', but that's fine, kngconfig['foo']['bar'].value would be our 'baz'.
#
# To achieve this, I used the __missing__ feature at the top dict level, added hybrid-dict features
# to KNGConfigItems (so that KNGConfigItems.__getattr__ will search the KNGConfigItem instances
# it contains for the provided index, or otherwise call a "_missing" API which works just like
# "__missing__" but, obviously is not a built-in magic name thingy so-preferably-not-to-speak.

# BUT, crap, I thought, this would mean that as soon as the API consumer simply looks at
# kngconfig['foo'], the 'foo' section must come into being.  Which wouldn't be a problem except
# that a 'kernelng_foo' package would fail to be generated during "kernelng overlay update" due
# to (amazingly!) there being no */foo package in all of portage.  Clearly this would not be what
# most API consumers meant by kngconfig['foo'].
#
# To solve this dilemma, I created the concept of "fetal" KNGConfigItem and KNGConfigItems instances.
# In this scheme, two new properties are created: "daddy" and "fetal".  Daddy maps back to the
# container that contains the instance (nb: implications wrt. i.e., deepclone() are not dealt with
# yet); meanwhile, fetal tells us:
#
#   KNGConfigItem: if the instance has never had a non-None "value" property set
#   KNGConfigItems: if the instance has ever had any non-fetal KNGConfigItem instances in it.
#
# Once these are "born", there is back-propogation through the "daddy"s so that the KNGConfigItems
# get born themselves, the instant they become grandparents, if necessary.
#
# The purpose of all these acrobatics is to censor the fetuses during deserialization, ensuring
# that no gross side effects occur due to the objects generated by __missing__ and _missing.
#
# Yes, I know this is all kinds of ugly but the interface is almost reasonable (eliminating the
# requirement to pass a "daddy" keyword argument to constructors would be nice and will eventually
# get done; the ability for multiple containers to be pregnant with the same fetus is not
# needed but my implementation also sort-of breaks the ability for multiple containers to contain
# the same non-fetal containee, which clearly sucks and should also be fixed).
#
# Each KNGConfigItem has a "reason" property which explains its semantic purpose.  Three "reasons"
# are supported: "stored" is the standard reason and simply means the KNGConfigItem represents
# a setting which should persist when the KNGConfig containing it is deserialized.  The "default"
# reason signifies that the key=>value mapping is not stored in the configuration file, and serves
# only as an in-memory means of tracking the default value (a default property also stores the
# default value if applicable; in this case, del(conf['foo']['bar']) will not delete the
# conf['foo']['bar'] KNGConfigItem from conf['foo'] -- instead it will set its reason to "default"
# which will cause the KNGConfigItem to disappear in the deserialized .conf file).  The third
# "reason" is as-yet unused and probably broken: "override" is intended to represent a temporary in-memory
# change to the configuration that will not persist.  The problem is that there is no provisions
# yet in place to track the persistent value being overriden.  Perhaps the "override" reason is not
# needed and can be removed.

class KNGConfigItem(object):
    def __init__(self, key, value='__comment__', default=None, reason=None, daddy=None):
        '''
        This constructor has two forms: KNGConfigItem(<comment-str>) and
        KNGConfigItem(<key>, <value>).  default and reason apply only to the second
        form -- for comments, the default is always None and the reason is always 'stored'
        '''
        if reason is not None:
           ValidateKNGConfigItemReason(key, value, reason)
        if value == '__comment__':
            key, value = value, key
            default=None
            reason='stored'
        elif reason is None and default is None:
            reason = 'stored'
        elif reason is None: # and default is set
            if value == default:
                # note: value is not None because default is not None
                reason = 'default'
            elif value is not None:
                reason = 'stored'
            # else, None is the right thing to have in reason for now, we'll have
            # to figure it out when we are born.
        self._key = key
        self._value = value
        if reason == 'default' and default is None:
            self._default = value
        else:
            self._default = default
        self._reason = reason
        self._daddy = daddy

    def __repr__(self):
        if self.iscomment:
            return 'KNGConfigItem(%r, reason=%r)' % (self.comment, self.reason)
        else:
            return 'KNGConfigItem(%r, %r, default=%r, reason=%r)' % (
                self.key, self.value, self.default, self.reason)

    @property
    def key(self):
        return self._key

    # note: "value" as a name for a property makes for confusing reading here but
    # foo.key/foo.value is imo a nice self-evident naming scheme for our consumers
    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, newvalue):
        if newvalue is None:
            # We need to know if we have left "fetal mode" during an assignment;
            # we track "fetal mode" using a convention that value == None <==> is_fetal
            # Values should always be strings anyhow (nb: I've deliberately opted not
            # to enforce that for pythonicicity reasons).
            raise ValueError('None is not an allowed value for KNGConfigItems.')
        if self._value == newvalue:
            # avoid any side-effects as no change is required.
            return
        if self._value is None:
            if self._daddy is None:
                raise ValueError('fetal-mode state-machine thinko')
            else:
                # it is possible that determining reason has been deferred 'till now
                if self._reason is None:
                    if self._default is None:
                        self._reason = 'stored'
                    elif newvalue == self._default:
                        self._reason = 'default'
                    else:
                        self._reason = 'stored'
                self._daddy.christen(self)
        if self.reason == 'default':
            # if the value has changed to a non-default value, then
            # reason will need to change to 'stored'.  Pretty sure the
            # newvalue != self._default is a noop but relying on that
            # here seems obscure and future-fragile.
            if self._default is not None and newvalue != self._default:
                self.reason = 'stored'
            # else: nothing to do: once stored, always stored.
        self._value = newvalue
    @value.deleter
    def value(self):
        if self._default is not None:
            self._value = self._default
            self._reason = 'default'
        elif self._daddy is not None:
            del self._daddy[self.key]
        else:
            raise ValueError('Unanticipated wierd corner case.  This is a bug.')

    @property
    def default(self):
        return self._default

    @property
    def reason(self):
        return self._reason
    @reason.setter
    def reason(self, value):
        ValidateKNGConfigItemReason(self.key, self.value, value)
        self._reason = value

    @property
    def fetal(self):
        return self._value is None

    @property
    def isexplicit(self):
        if self.reason == 'default':
            return False
        elif self.reason == 'override':
            # FIXME: This result suggests "isexplicit" is the wrong name for this.
            return False
        elif self.value is None:
            # fetal mode
            return False
        else:
            return True

    @property
    def iscomment(self):
        return (self.key == '__comment__')

    @property
    def comment(self):
        return self.value

    @property
    def daddy(self):
        return self._daddy

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

    # format of the innermost key=>val tuples:
    # ( key, val, [force_stored=False, [no_default=False]] )
    result['implicit_global'] = (
        '# %(framework)s.conf',
        '',
        '# This file is designed to contain sensible default values for',
        '# a plurality of real-world systems; however, it can and often should',
        '# be modified to match your system\'s needs.',
        '#',
        '# %(framework)s.conf has a "Windows .ini"-style syntax, consisting of',
        '# name => value mappings, i.e.:',
        '#',
        '#     <name> = <value>',
        '#',
        '# and section headings enclosed in brackets, i.e.:',
        '#',
        '#     [<section>]',
        '#',
        '# Each section (with one exception, described below) corresponds to',
        '# a portage package atom.  For example, the header:',
        '#',
        '#     [=sys-kernel/gentoo-sources-3.15*]',
        '#',
        '# would contain specifics about how to map from portage packages',
        '# matching the "=sys-kernel/gentoo-sources-3.15*" portage "atom"',
        '# to %(framework)s packages in the site-specific %(framework)s',
        '# overlay (n.b.: the %(prog)s utility contains all the secret sauce to',
        '# create and maintain these site-specific overlays.  Run "%(prog)s -h",',
        '# or "man %(prog)s" if that\'s Greek to you, and you\'re not Greek).',
        '#',
        '# Lines beginning with a "#" are treated as comments.  Empty lines',
        '# are ignored.  Quotation marks are not needed and will not be',
        '# preserved by the %(prog)s utility -- their use is discouraged.',
        '#',
        '# A "[global]" section is also supported.  Any "<name> = <value>"',
        '# pairs appearing before any section header are considered',
        '# implicitly to be in the global section, so the "[global]" header',
        '# may be omitted, so long as all global settings come first.',
        '',
    )
    result['global'] = (
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
        '# name_prefix',
        '# ==========',
        '# default value: %(prog)s_',
        '# scope: any',
        '#',
        '# Prefix applied to ng-sources package names in the overlay.  For',
        '# example, if name_prefix is "foo", then the %(framework)s package',
        '# mirroring portage kernel package sys-kernel/bar-sources in the',
        '# %(framework)s overlay would be named sys-kernel/foobar-sources.',
        '# Making this empty would result in identically named packages and',
        '# is therefore strongly discouraged, although not technocratically',
        '# prohibited by %(progdesc)s.',
        '',
        ( 'name_prefix', '%(prog)s_' ),
        '',
        '# no_name_prefix',
        '# ==============',
        '# default value: no_',
        '# scope: any',
        '#',
        '# Prefix applied to no-sources package names in the overlay.  For',
        '# example, if no_name_prefix is "no_", then the no-sources package',
        '# mirroring the portage kernel package sys-kernel/shit-sources in',
        '# the %(framework)s overlay would be named sys-kernel/no_shit-sources.',
        '# Making this empty would result in identically named packages and',
        '# is therefore strongly discouraged, although not technocratically',
        '# prohibited by %(progdesc)s.',
        '',
        ( 'no_name_prefix', 'no_' ),
        '',
        '# repos_conf',
        '# ==========',
        '# default value: %(eprefix)s/etc/portage/repos.conf',
        '# scope: global only',
        '#',
        '# Location of portage\'s repos.conf file.  If empty, i.e.:',
        '#',
        '#     repos_conf =',
        '#',
        '# %(framework)s will not automatically maintain the repos.conf file;',
        '# otherwise, when the overlay is created, this file will be',
        '# automatically modified to activate the %(framework)s overlay in',
        '# portage if and when the overlay is created.',
        '',
        ( 'repos_conf', '%(eprefix)s/etc/portage/repos.conf' ),
        '',
    )
    result['sys-kernel/gentoo-sources'] = (
        '',
        '# name_override',
        '# =============',
        '# No default value',
        '# scope: sectional only',
        '#',
        '# Instead of the name_prefix scheme, it is possible to specify a',
        '# name explicitly for the overlay packages generated by %(progdesc)s',
        '# to mirror the portage package in a given section.  For example,',
        '# if we put name_override = %(prog)s in the [sys-kernel/gentoo-sources]',
        '# section, then the overlay package mirroring sys-kernel/gentoo-sources',
        '# generated by %(progdesc)s would be named sys-kernel/%(prog)s.',
        '',
        ( 'name_override', '%(prog)s-sources', True, True ),
        '',
        '# no_name_override',
        '# ================',
        '# No default value',
        '# scope: sectional only',
        '#',
        '# Instead of the no_name_prefix scheme, it is possible to specify a',
        '# name explicitly for the no-sources overlay packages generated by',
        '# %(progdesc)s to mirror the portage package in a given section.  For',
        '# example if we put no_name_override = nope in the',
        '# [sys-kernel/gentoo-sources] section, then the no-sources package',
        '# mirroring sys-kernel/gentoo-sources in the overlay generated by',
        '# %(progdesc)s would be named sys-kernel/nope.',
        '',
        ( 'no_name_override', 'no-sources', True, True ),
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
        if isinstance(valitem, tuple) and (len(valitem) < 4 or not valitem[3])
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
    def __init__(self, *args, **kwargs):
        if 'fetal' in kwargs:
            self._fetal = kwargs.pop('fetal')
        else:
            self._fetal = False
        if 'daddy' in kwargs:
            self._daddy = kwargs.pop('daddy')
        else:
            self._daddy = None
        if self._fetal and self._daddy is None:
            raise TypeError('KNGConfigItems.__init__: fetal requires daddy.')
        super(KNGConfigItems, self).__init__(*args, **kwargs)

    @property
    def fetal(self):
        return self.is_fetal()

    def is_fetal(self):
        return self._fetal

    def __contains__(self, key):
        for item in self:
            if item.key == key:
                return True
        return super(KNGConfigItems, self).__contains__(key)

    def __repr__(self):
        return 'KNGConfigItems(%s)' % super(KNGConfigItems, self).__repr__()

    def iterkeypairs(self):
        return ( (item.key, item.value) for item in self if (not item.fetal) and (not item.iscomment) )
    def iterkeys(self):
        return ( item[0] for item in self.iterkeypairs() )
    def itervalues(self):
        return ( item[1] for item in self.iterkeypairs() )
    def iterexplicit(self):
        return ( item for item in self if item.isexplicit )

    def find_default(self, key):
        '''
        Returns any default that would be associated with the provided key in
        the current section or None, if none can be found, using the global
        defaults dict.  Raises TypeError if we have no daddy.
        '''
        if self._daddy is None:
            raise TypeError('find_default requires daddy')
        if self._daddy.section_of(self) in ['global', 'implicit_global']:
            if key in KNGGlobalDefaults():
                return KNGGlobalDefaults()[key]
        return None

    def __getitem__(self, index):
        if isinstance(index, slice) or isinstance(index, int):
            return super(KNGConfigItems, self).__getitem__(index)
        for item in self:
            if (not item.iscomment) and item.key == index:
                # note: this will return any existing "fetus" with the requested key.
                return item
        return self._missing(index)
    def _missing(self, key):
        # add a "fetal" KNGConfigItem for the provided key, analogous to __missing__ in dict
        rv = KNGConfigItem(key, None, default=self.find_default(key), daddy=self)
        self.append(rv)
        return rv

    def __setitem__(self, index, value):
        if value is None:
            raise ValueError('KNGConfigItems.__setitem__: use del instead? assigning None is prohibited.')
        elif index == '__comment__':
            # always treat this as a request to append a new comment
            self._fetal = False
            self.append(KNGConfigItem(value, daddy=self))
            return
        elif isinstance(index, slice) or isinstance(index, int):
            if self._fetal and isinstance(value, KNGConfigItem) and not value.fetal:
                self._fetal = False
            super(KNGConfigItems, self).__setitem__(index, value)
            return
        for itemindex, item in enumerate(self):
            if (not item.iscomment) and item.key == index:
                if isinstance(value, KNGConfigItem):
                    if not value.fetal:
                        self._fetal = False
                    self[itemindex] = value
                    return
                else:
                    item.value = value
                    return
        if isinstance(value, KNGConfigItem):
            self.append(value)
        else:
            self.append(KNGConfigItem(index, value, daddy=self))

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
        if isinstance(value, KNGConfigItem):
            if not value.fetal:
                self._fetal = False
    def extend(self, values):
        for v in values:
            self.append(v)
    def pop(self, index=-1):
        v = self[index]
        del self[index]
        return v

    def christen(self, item):
        # item is not used ATM, this is just a notification that we now have at least
        # one nonfetal item, which is enough.
        self._fetal = False

    def __iadd__(self, values):
        self.extend(values)
        return self

    def __imul__(self, value):
        raise NotImplementedError('KNGConfigItems.__imul__')
    def __mul__ (self, other):
        raise NotImplementedError('KNGConfigItems.__mul__')
    def __rmul__ (self, other):
        raise NotImplementedError('KNGConfigItems.__rmul__')

class KNGGlobalConfigItemsProxy(KNGConfigItems):
    def __init__(self, daddy):
        self._implicit = daddy['implicit_global']
        self._explicit = daddy['global']
        super(KNGGlobalConfigItemsProxy, self).__init__(daddy=daddy, fetal=self.fetal)

    def __contains__(self, key):
        return self._implicit.__contains__(key) or self._explicit.__contains__(key)

    def __len__(self):
        return len(self._implicit) + len(self._explicit)

    def _fake_self_for_query(self):
        return list(self._implicit) + list(self._explicit)

    def _fake_self_for_append(self):
        if not self._explicit.fetal:
            return self._explicit
        elif not self._implicit.fetal:
            return self._implicit
        else:
            return self._explicit

    def __repr__(self):
        return 'KNGConfigItems(%s)' % self._fake_self_for_query()

    def is_fetal(self):
        return self._implicit.fetal and self._explicit.fetal

    def iterkeypairs(self):
        return (
            (item.key, item.value)
            for item in self._fake_self_for_query()
            if (not item.fetal) and (not item.iscomment)
        )
    def iterkeys(self):
        return ( item[0] for item in self.iterkeypairs() )
    def itervalues(self):
        return ( item[1] for item in self.iterkeypairs() )
    def iterexplicit(self):
        return ( item for item in self._fake_self_for_query() if item.isexplicit )

    def find_default(self, key):
        '''
        Returns any default that would be associated with the provided key in
        the current section or None, if none can be found, using the global
        defaults dict.  Raises TypeError if we have no daddy.
        '''
        # section_of won't work but thankfully we don't need it!
        if key in KNGGlobalDefaults():
            return KNGGlobalDefaults()[key]
        return None

    def __getitem__(self, index):
        if isinstance(index, slice) or isinstance(index, int):
            return self._fake_self_for_query().__getitem__(index)
        for item in self._fake_self_for_query():
            if (not item.iscomment) and item.key == index:
                # note: this will return any existing "fetus" with the requested key.
                return item
        return self._missing(index)
    def _missing(self, key):
        # add a "fetal" KNGConfigItem for the provided key, analogous to __missing__ in dict
        real_daddy=self._fake_self_for_append()
        rv = KNGConfigItem(key, None, default=self.find_default(key), daddy=real_daddy)
        real_daddy.append(rv)
        return rv

    def __setitem__(self, index, value):
        if value is None:
            raise ValueError('KNGGlobalConfigItemsProxy.__setitem__: use del instead? assigning None is prohibited.')
        elif index == '__comment__':
            # always treat this as a request to append a new comment
            real_daddy = self._fake_self_for_append()
            real_daddy._fetal = False
            real_daddy.append(KNGConfigItem(value, daddy=real_daddy))
            return
        elif isinstance(index, int):
            if index >= len(self._implicit):
                self._explicit[index - len(self._implicit)] = value
            else:
                self._implicit[index] = value
            return
        elif isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            if step != 1:
                raise NotImplementedError('Fancy stepping behavior not supported here.')
            if start < len(self._implicit) and stop > len(self._implicit):
                raise NotImplementedError('No soap, honky-lips: %s, %s.' % (slice(start,stop,step), len(self._implicit)))
            if start < len(self._implicit):
                self._implicit[slice(start,stop,step)] = value
            else:
                start -= len(self._implicit)
                stop -= len(self._implicit)
                self._explicit[slice(start, stop, step)] = value
            return
            # done!
        for (itemindex, item), realdeal in chain(zip(enumerate(self._implicit), repeat(self._implicit)),
                                                 zip(enumerate(self._explicit), repeat(self._explicit))):
            if (not item.iscomment) and item.key == index:
                if isinstance(value, KNGConfigItem):
                    # this is fucked, what if daddy didn't match up?  just copy the value i guess...
                    # FIXME
                    realdeal[itemindex].value = value.value
                    return
                else:
                    item.value = value
                    return
        if isinstance(value, KNGConfigItem):
            self._fake_self_for_append().append(value)
        else:
            self._fake_self_for_append().append(KNGConfigItem(index, value, daddy=self))

    def __delitem__(self, index):
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            if step != 1:
                raise NotImplementedError('Fancy stepping behavior not supported here.')
            if start < len(self._implicit) and stop > len(self._implicit):
                raise NotImplementedError('No soap, honky-lips: %s, %s.' % (slice(start,stop,step), len(self._implicit)))
            if start < len(self._implicit):
                del(self._implicit[slice(start,stop,step)])
            else:
                start -= len(self._implicit)
                stop -= len(self._implicit)
                del(self._explicit[slice(start, stop, step)])
            return
        elif isinstance(index, int):
            if index >= len(self._implicit):
                del(self._explicit[index - len(self._implicit)])
            else:
                del(self._implicit[index])
            return

        for (itemindex, item), realdeal in chain(zip(enumerate(self._implicit), repeat(self._implicit)),
                                                 zip(enumerate(self._explicit), repeat(self._explicit))):
            if (not item.iscomment) and item.key == index:
                del(realdeal[itemindex])
                return
        raise IndexError('Could not find item matching index "%s" in %s to delete' % (index, self))

    def insert(self, index, value):
        if isinstance(index, int):
            if index < len(self._implicit):
                self._implicit.insert(index, value)
            else:
                self._explicit.insert(index - len(self._implicit), value)
            return
        for (itemindex, item), realdeal in chain(zip(enumerate(self._implicit), repeat(self._implicit)),
                                                 zip(enumerate(self._explicit), repeat(self._explicit))):
            if (not item.iscomment) and item.key == index:
                realdeal.insert(itemindex, value)
                return
        raise IndexError('Could not find item matching insertion index "%s" in %s' % (index, self))

    def append(self, value):
        for (itemindex, item), realdeal in chain(zip(enumerate(self._implicit), repeat(self._implicit)),
                                                 zip(enumerate(self._explicit), repeat(self._explicit))):
            if (not item.iscomment) and item.key == value.key:
                del(realdeal[itemindex])
                realdeal.append(value)
                return
        self._fake_self_for_append().append(value)

    def clear(self):
        self._implicit.clear()
        self._explicit.clear()

    def index(self, *args):
        return self._fake_self_for_query().index(*args)

    def pop(self, index=None):
        if index is None:
            index = len(self) - 1
        if index >= len(self._implicit):
            return self._explicit.pop(index - len(self._implicit))
        else:
            return self._implicit.pop(index)

    def remove(self, value):
        if value in self._implicit:
            self._implicit.remove(value)
        else:
            self._explicit.remove(value)

    def reverse(self):
        raise NotImplementedError('KNGGlobalCojnfigItemsProxy.reverse')

    def __eq__(self, other):
        return self._fake_self_for_query().__eq__(other)

    def __ge__(self, other):
        return self._fake_self_for_query().__ge__(other)

    def __gt__(self, other):
        return self._fake_self_for_query().__gt__(other)

    def __hash__(self):
        return self._fake_self_for_query().__hash__()

    def __iter__(self, *args, **kwargs):
        return self._fake_self_for_query().__iter__(*args, **kwargs)

    def __le__(self, other):
        return self._fake_self_for_query().__le__(other)

    def __lt__(self, other):
        return self._fake_self_for_query().__lt__(other)

    def __ne__(self, other):
        return self._fake_self_for_query().__ne__(other)

    def sort(self):
        raise NotImplementedError('KNGGlobalConfigItemsProxy.sort')

    def __reversed__(self):
        raise NotImplementedError('KNGGlobalConfigItemsProxy.__reversed__')

    def __sizeof__(self):
        return self._implicit.__sizeof__() + self._explicit.__sizeof__()

    def christen(self, item):
        # should never happen since the KNGConfigItems should have the "real" daddys
        raise NotImplementedError('KNGGlobalConfigItemsProxy.christen!?')

class KNGConfig(OrderedDict):
    def __init__(self, kernelng_conf_file=KERNELNG_CONF_FILE, repos_conf_file=REPOS_CONF_FILE):
        self._kernelng_conf_file = kernelng_conf_file
        self._repos_conf_file = repos_conf_file
        super(KNGConfig, self).__init__()

    def section_of(self, configitems):
        for section, cfgitems in list(self.items()):
            if cfgitems is configitems:
                return section
        raise ValueError(configitems)

    def loadExampleConfig(self):
        self.clear()
        ecd = KNGExampleConfigData()
        for key in ecd.keys():
            self[key] = KNGConfigItems(daddy=self)
            val = ecd[key]
            for item in val:
                if isinstance(item, tuple):
                    if len(item) > 3 and item[3]:
                        # when item[3] is true (no default), then this config. parameter will
                        # not appear in KNGGlobalDefaults and therefore stored, no default is the only
                        # sensible interpretation regardless of item[2] (force-stored).
                        self[key].append(KNGConfigItem(item[0], item[1], reason='stored', daddy=self[key]))
                    elif len(item) > 2 and item[2]:
                        # When item[3] is False (meaning, the config. parameter item[0] does have
                        # a default value and it's item[1]), but item[2] is true, this amounts to
                        # saying "item[0] is set to item[1], which happens to be the default value,
                        # but despite this, please force the config. parameter to appear in the .conf
                        # file anyhow.  We achieve this miracle like so:
                        self[key].append(KNGConfigItem(item[0], item[1], default=item[1], reason='stored', daddy=self[key]))
                    else:
                        # add a comment item "illustrating" the default value in "pseudo-prose", as, otherwise,
                        # the KNGConfigItem for the item[0] => item[1] setting would not appear anywhere in the
                        # example configuration file (because its reason will be 'default', not 'stored')
                        self[key].append(KNGConfigItem('# %(confkey)s = %(confval)s' % {
                            'confkey': item[0], 'confval': item[1] }))
                        # add the KNGConfigItem mapping the config. parameter to its default value
                        self[key].append(KNGConfigItem(item[0], item[1], default=item[1], reason='default', daddy=self[key]))
                else:
                    self[key].append(KNGConfigItem(item, daddy=self[key]))

    @property
    def globals(self):
        '''
        Returns a virtualized KNGConfigItems proxy which treats the 'global' and 'implicit_global'
        sections as a unified section.  This helps prevent accidental mistakes like adding the
        same configuration key to both sections, and simplifies various usages.  When both global
        and implicit_global sections exist, new items go into the explicit global section; when
        only one of these sections exist, new items go into it; when neither section exists, new
        items go into an explicit global section which will be created on demand.
        '''
        return KNGGlobalConfigItemsProxy(self)
    def writeConfigText(self, file=None):
        '''
        Write the currently loaded configuration to a given file.

        :param file: If provided, the output will be written into the provided click.File object.
                     If not provided, output will go to standard output.
        '''
        keys = self.keys()
        for key in keys:
            vlist = self[key]
            if vlist and not vlist.fetal:
                if key != 'implicit_global':
                    click.echo('[%s]' % key, file=file)
                for item in vlist.iterexplicit():
                    if item.iscomment:
                        click.echo(item.comment, file=file)
                    else:
                        click.echo('%(itemkey)s = %(itemvalue)s' % { 'itemkey': item.key, 'itemvalue': item.value }, file=file)

    def __missing__(self, index):
        rv=KNGConfigItems(fetal=True, daddy=self)
        self[index] = rv
        return rv
