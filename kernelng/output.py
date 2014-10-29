#!/usr/bin/env python
#-*- coding:utf-8 -*-
# vim:ai:sta:et:ts=4:sw=4:sts=4

"""kernelng 0.x
 Tool for maintaining customized overlays of kernel-ng.eclass-based ebuilds

Copyright 2005-2014 Gentoo Foundation

	Copyright (C) 2005 Colin Kingsley <tercel@gentoo.org>
	Copyright (C) 2008 Zac Medico <zmedico@gentoo.org>
	Copyright (C) 2009 Sebastian Pipping <sebastian@pipping.org>
	Copyright (C) 2009 Christian Ruppert <idl0r@gentoo.org>
	Copyright (C) 2012 Brian Dolbec <dolsen@gentoo.org>
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

import sys
import re
import codecs
import locale
import os

from argparse import HelpFormatter
from functools import wraps
import click

def encoder(text, _encoding_):
    return codecs.encode(text, _encoding_, 'replace')

def decode_selection(selection):
    '''utility function to decode a list of strings
    accoring to the filesystem encoding
    '''
    # fix None passed in, return an empty list
    selection = selection or []
    enc = sys.getfilesystemencoding()
    if enc is not None:
        return [encoder(i, enc) for i in selection]
    return selection

def get_encoding(output):
    if hasattr(output, 'encoding') \
            and output.encoding != None:
        return output.encoding
    else:
        encoding = locale.getpreferredencoding()
        # Make sure that python knows the encoding. Bug 350156
        try:
            # We don't care about what is returned, we just want to
            # verify that we can find a codec.
            codecs.lookup(encoding)
        except LookupError:
            # Python does not know the encoding, so use utf-8.
            encoding = 'utf_8'
        return encoding

verbose_level = 1
VERBOSE_REVERSE={0: '--quiet', 1: '(default)', 2: '--verbose', 3: '--debug'}

def has_verbose_level(l):
    return verbose_level >= l

def set_verbose_level(ctx, option, value):
    global verbose_level
    if value is None:
        return
    if value != 1 and verbose_level != 1 and value != verbose_level:
        ctx.fail('Conflicting verbose options %s and %s specified simultaneously.' % 
            (VERBOSE_REVERSE[verbose_level], VERBOSE_REVERSE[value]))
    else:
        verbose_level = value

def echov(message=None, vl=1, file=None, nl=True, err=None):
    if verbose_level >= vl:
        if err is None:
            if vl>= 3:
                err=True
            else:
                err=False
        click.echo(message, file, nl, err)

def sechov(text, vl=1, file=None, nl=True, err=None, **styles):
    if verbose_level >= vl:
        if err is None:
            if vl>= 3:
                err=True
            else:
                err=False
        click.secho(text, file, nl, err, **styles)

_string_types=None

def _init_stringtypes():
    strtypes=[ type('') ]
    try:
        strtypes.append(basestring)
    except NameError:
        pass
    btype=type(b'')
    if btype not in strtypes:
        strtypes.append(btype)
    try:
        eval("strtypes.append(type(u''))")
    except SyntaxError:
        pass

    global _string_types
    _string_types = tuple(set(strtypes))

if _string_types is None:
    _init_stringtypes()

def is_string(thing):
    return isinstance(thing, _string_types)

class AutoTracer(object):
    def __init__(self):
        self._indent = 0
    def style_fn(self, f, arglist):
        return ''.join((
            '  ' * min(self._indent, 20),
            click.style(f, fg='blue', bold=True),
            click.style('(', fg='white', bold=True),
            self._style_arglist(arglist),
            click.style(')', fg='white', bold=True),
        ))

    def style_rvfn(self, f, rv):
        return ''.join((
            '  ' * max(min(self._indent - 1, 20), 0),
            click.style(f, fg='blue', bold=True),
            click.style('()', fg='white', bold=True),
            ' ',
            click.style('<--', fg='green', bold=True),
            ' ',
            self._style_argval(rv)
        ))
    def style_m(self, mi, m, arglist):
        return ''.join((
            '  ' * min(self._indent, 20),
            self._style_obj(mi, m),
            click.style('.', fg='white', bold=True),
            click.style(m, fg='blue', bold=True),
            click.style('(', fg='white', bold=True),
            self._style_arglist(arglist),
            click.style(')', fg='white', bold=True),
        ))

    def style_rvm(self, mi, m, rv):
        return ''.join((
            '  ' * max(min(self._indent - 1, 20), 0),
            self._style_obj(mi, m),
            click.style('.', fg='white', bold=True),
            click.style(m, fg='blue', bold=True),
            click.style('()', fg='white', bold=True),
            ' ',
            click.style('<--', fg='green', bold=True),
            ' ',
            self._style_argval(rv),
        ))
    def _style_obj(self, mi, m):
        try:
            if m in ['__repr__', '__str__']:
                return 'inst:%s' % click.style(mi.__class__.__name__, fg='yellow', bold=True)
            rv = str(mi)
            if len(rv) > 15:
                return 'inst:%s' % click.style(mi.__class__.__name__, fg='yellow', bold=True)
            else:
                rv = click.style(rv, fg='yellow', bold=True)
                return rv
        except:
            return 'inst:%s' % click.style(mi.__class__.__name__, fg='yellow', bold=True)


    def _style_argval(self, val):
        try:
            wuz_string = False
            if is_string(val):
                rv=repr(val)
                wuz_string = True
            elif val is None:
                rv='<None>'
            else:
                rv=str(val)
            if len(rv) > 15:
                if wuz_string:
                    rv = "<%s'...>" % rv[:9]
                else:
                    rv = '[%s...]' % rv[:10]
            rv = click.style(rv, fg='cyan', bold=True)
            return rv
        except:
            try:
                return click.style('<unprintable:%s>' % val.__class__.__name__, fg='red', bold=True)
            except:
                return click.style('<unprintable:WTF?>', fg='red', bold=True)

    def _style_arg(self, argtuple):
        if len(argtuple) > 1:
            return ''.join((
                '%s=' % argtuple[1],
                self._style_argval(argtuple[0])
            ))
        else:
            return self._style_argval(argtuple[0])

    def _style_arglist(self, arglist):
        if len(arglist) > 10:
            newarglist = arglist[:18]
            newarglist.append( ('<< %d SKIPPED ARGS >>' % len(arglist) - 18,) )
            newarglist.append(arglist[-1])
            arglist = newarglist
        return ', '.join((
            [self._style_arg(argtuple) for argtuple in arglist]
        ))

    def say(self, lambdasomething):
        if has_verbose_level(3):
            echov(lambdasomething(), err=True)

    def indent(self):
        self._indent += 1
    def dedent(self):
        self._indent -= 1
        if self._indent < 0:
            # oops, fuck it, I guess
            self._indent = 0

_at = AutoTracer()

def auto_trace_function(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        _at.say(
            lambda: _at.style_fn(
                f.__name__,
                tuple(((arg,) for arg in args)) + tuple(((val, kw) for kw, val in iter(kwargs.items())))
            )
        )
        _at.indent()
        try:
            rv = f(*args, **kwargs)
            _at.say(lambda: _at.style_rvfn(f.__name__, rv))
            return rv
        finally:
            _at.dedent()
    return wrapper

def auto_trace_method(m):
    @wraps(m)
    def methodwrapper(self, *args, **kwargs):
        _at.say(
            lambda: _at.style_m(
                self,
                m.__name__,
                tuple(((arg,) for arg in args)) + tuple(((val, kw) for kw, val in iter(kwargs.items())))
            )
        )
        _at.indent()
        try:
            rv = m(self, *args, **kwargs)
            _at.say(lambda: _at.style_rvm(self, m.__name__, rv))
            return rv
        finally:
            _at.dedent()
    return methodwrapper
