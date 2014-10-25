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
