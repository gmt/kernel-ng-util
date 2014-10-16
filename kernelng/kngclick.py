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

from __future__ import print_function

from click.core import Context, Command, Group
from click.termui import style
from click.formatting import HelpFormatter
from click.decorators import command

class KNGHelpFormatter(HelpFormatter):
    def write_usage(self, prog, args='', prefix='Usage: '):
        prog = style(prog, fg='white', bold=True)
        super(KNGHelpFormatter, self).write_usage(prog, args, prefix)

class KNGContext(Context):
    def make_formatter(self):
        return KNGHelpFormatter(width=self.terminal_width)

class KNGGroup(Group):
    def make_context(self, info_name, args, parent=None, **extra):
        for key, value in iter((self.context_settings or {}).items()):
            if key not in extra:
                extra[key] = value
        ctx = KNGContext(self, info_name=info_name, parent=parent, **extra)
        self.parse_args(ctx, args)
        return ctx
    def kngcommand(self, *args, **kwargs):
        def decorator(f):
            cmd = kngcommand(*args, **kwargs)(f)
            self.add_command(cmd)
            return cmd
        return decorator
    def knggroup(self, *args, **kwargs):
        def decorator(f):
            cmd = knggroup(*args, **kwargs)(f)
            self.add_command(cmd)
            return cmd
        return decorator

class KNGCommand(Command):
    def make_context(self, info_name, args, parent=None, **extra):
        for key, value in iter((self.context_settings or {}).items()):
            if key not in extra:
                extra[key] = value
        ctx = KNGContext(self, info_name=info_name, parent=parent, **extra)
        self.parse_args(ctx, args)
        return ctx
    def kngcommand(self, *args, **kwargs):
        def decorator(f):
            cmd = kngcommand(*args, **kwargs)(f)
            self.add_command(cmd)
            return cmd
        return decorator
    def knggroup(self, *args, **kwargs):
        def decorator(f):
            cmd = knggroup(*args, **kwargs)(f)
            self.add_command(cmd)
            return cmd
        return decorator

def kngcommand(name=None, **kwargs):
    kwargs.setdefault('cls', KNGCommand)
    return command(name, **kwargs)

def knggroup(name=None, **kwargs):
    kwargs.setdefault('cls', KNGGroup)
    return command(name, **kwargs)

