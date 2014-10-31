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
from functools import wraps, partial
from inspect import isclass, ismethod
from .utils import is_string
import wrapt
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

# we use this dummy as an alternative to None so that valid NoneType keyword arguments
# can be distinguished from missing arguments.
_seriously_invalid_argument = object()

class AutoTracer(object):
    def __init__(self):
        self._indent = 0
        self._suppression = 0

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
            self._style_obj(rv, objcolor='magenta')
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

    def style_cm(self, cls, cm, arglist):
        return ''.join((
            '  ' * min(self._indent, 20),
            '<',
            click.style(mc.__name__, fg='yellow', bold=True),
            ' class>',
            click.style('.', fg='white', bold=True),
            click.style(cm, fg='blue', bold=True),
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
            self._style_obj(rv, objcolor='magenta'),
        ))

    def style_rvcm(self, cls, cm, rv):
        return ''.join((
            '  ' * max(min(self._indent - 1, 20), 0),
            '<',
            click.style(cls.__name__, fg='yellow', bold=True),
            ' class>',
            click.style('.', fg='white', bold=True),
            click.style(cm, fg='blue', bold=True),
            click.style('()', fg='white', bold=True),
            ' ',
            click.style('<--', fg='green', bold=True),
            ' ',
            self._style_obj(rv, objcolor='magenta'),
        ))

    def _errobj_style(self, obj, e, objcolor='yellow'):
        try:
            return '%s%s<%s%s%s>%s' % (
                click.style(obj.__class__.__name__, fg=objcolor, bold=True),
                click.style('(', fg='white', bold=True),
                click.style('WTF', fg='red', bold=True),
                click.style(':', fg='white', bold=False),
                click.style(repr(e), fg='red', bold=False),
                click.style(')', fg='white', bold=True)
            )
        except Exception as e:
            try:
                return '<WTF:%s>' % str(e)
            except:
                return '<OMGWTFBBQ>'

    def _style_obj(self, mi, m=None, objcolor='yellow'):
        try:
            if m in ['__repr__', '__str__', '__getattr__', '__getitem__']:
                return '%s%s' % (
                    click.style(mi.__class__.__name__, fg=objcolor, bold=True),
                    click.style('()', fg='white', bold=True)
                )
            if mi is None:
                return click.style('<None>', fg=objcolor, bold=True)
            elif isinstance(mi, bool):
                return click.style('%r' % mi, fg=objcolor, bold=True)
            rv = repr(mi)
            if len(rv) > 20:
                if is_string(mi):
                    return("%s%s...%s%s" % (
                        click.style(rv[0], fg='white', bold=True),
                        click.style(rv[1:8], fg=objcolor, bold=True),
                        click.style(rv[-7:-1], fg=objcolor, bold=True),
                        click.style(rv[-1], fg='white', bold=True)
                    ))
                else:
                    rv = '[%s...%s]' % (
                            click.style(rv[:8], fg='magenta', bold=False),
                            click.style(rv[-7:], fg='magenta', bold=False)
                    )
            else:
                if is_string(mi):
                    return click.style(rv, fg=objcolor, bold=True)
                else:
                    rv = click.style(rv, fg='magenta', bold=False)

            return '%s%s%s%s' % (
                click.style(mi.__class__.__name__, fg=objcolor, bold=True),
                click.style('(', fg='white', bold=True),
                rv,
                click.style(')', fg='white', bold=True)
            )
        except Exception as e:
            return self._errobj_style(mi, e)

    def _style_argval(self, val):
        return self._style_obj(val, objcolor='cyan')

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

    def say(self, lambdasomething, warning=False, arg=_seriously_invalid_argument):
        if self._suppression <= 0 and has_verbose_level(3) or (warning and has_verbose_level(1)):
            if arg is not _seriously_invalid_argument:
                echov(lambdasomething(arg), err=True)
            else:
                echov(lambdasomething(), err=True)

    def indent(self):
        self._indent += 1
    def dedent(self):
        self._indent -= 1
        if self._indent < 0:
            # oops, fuck it, I guess
            self._indent = 0
    def suppress(self):
        self._suppression += 1
    def unsuppress(self):
        self._suppression -= 1

_at = AutoTracer()

def trace(wrapped=None, warning=False):
    if wrapped is None:
        return partial(trace, warning=warning)

    @wrapt.decorator
    def trace_decorator(wrapped, instance, args, kwargs):
        if instance is None:
            if isclass(wrapped):
                # class
                raise TypeError('trace decorator applied to class object: %r' % wrapped)
            else:
                # function or staticmethod
                lambda_pre = lambda: _at.style_fn(
                    wrapped.__name__,
                    tuple(((arg,) for arg in args)) + tuple(((val, kw) for kw, val in iter(kwargs.items())))
                )
                lambda_post = lambda rv: _at.style_rvfn(wrapped.__name__, rv)
        else:
            if isclass(instance):
                # classmethod
                lambda_pre = lambda: _at.style_cm(
                    instance,
                    wrapped.__name__,
                    tuple(((arg,) for arg in args)) + tuple(((val, kw) for kw, val in iter(kwargs.items())))
                )
                lambda_post = lambda rv: _at.style_rvcm(instance, wrapped.__name__, rv)
            else:
                # instancemethod
                lambda_pre = lambda: _at.style_m(
                    instance,
                    wrapped.__name__,
                    tuple(((arg,) for arg in args)) + tuple(((val, kw) for kw, val in iter(kwargs.items())))
                )
                lambda_post = lambda rv: _at.style_rvm(instance, wrapped.__name__, rv)

        # in each case the rest of the recipe is now the same:
        _at.say(lambda_pre, warning=warning)
        _at.indent()
        try:
            rv = wrapped(*args, **kwargs)
            _at.say(lambda_post, warning=warning, arg=rv)
            return rv
        finally:
            _at.dedent()

    return trace_decorator(wrapped)

def suppress_tracing(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        _at.suppress()
        try:
            return f(*args, **kwargs)
        finally:
            _at.unsuppress()
    return wrapper
