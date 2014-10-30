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

