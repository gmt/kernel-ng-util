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

import sys
import os
import re

import click
from kernelng.kngclick import kngcommand, knggroup

# This block ensures that ^C interrupts are handled quietly.
try:
    import signal

    def exithandler(signum,frame):
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        click.echo('Caught signal %s. Exiting' % signum)
        sys.exit(1)

    signal.signal(signal.SIGINT, exithandler)
    signal.signal(signal.SIGTERM, exithandler)
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    # eprefix compatibility
    try:
        from portage.const import rootuid
    except ImportError:
        rootuid = 0

    # establish the eprefix, initially set so eprefixify can
    # set it on install
    EPREFIX = "@GENTOO_PORTAGE_EPREFIX@"

    # check and set it if it wasn't
    if EPREFIX == "@GENTOO_%s_EPREFIX@" % "PORTAGE":
        EPREFIX = ''

    PROGNAME = sys.argv[0].split(os.path.sep)[-1] if len(sys.argv) >= 1 else 'kernelng'
    PROGDESC = 'kernel-ng-util'

    HS_RE = re.compile('%\([^)]*\)[^\W\d_]', re.UNICODE)
    HS = {
        'prog': click.style(PROGNAME, fg='white', bold=True),
        'progdesc': PROGDESC,
        'eprefix': EPREFIX,
    }
    def hs(text):
        return text % HS if re.search(HS_RE, text) else text

    CONTEXT_SETTINGS = dict(
        help_option_names = ['-h', '--help']
    )

    @knggroup(
        PROGNAME,
        context_settings=CONTEXT_SETTINGS,
        help = hs(
            """
            A utility to manage a site-specific overlay containing
            customized %(progdesc)s packages.

            A minimal workflow could be as follows:

            \b
              $ sudo %(prog)s config -i
              $ sudo %(prog)s overlay create
              $ sudo %(prog)s ebuild create ng
              $ sudo emerge -u @world
            """
        )
    )
    def cli():
        pass

    @cli.knggroup(
        help = hs(
            """
            Manage the %(progdesc)s overlay
            """
        )
    )
    def overlay():
        pass

    @overlay.kngcommand(
        help = hs(
            """
            Create and activate an empty %(progdesc)s overlay
            """
        )
    )
    def create():
        pass

    @overlay.kngcommand(
        help = hs(
            """
            Deactivate or remove the %(progdesc)s overlay
            """
        )
    )
    def destroy():
        pass

    @cli.knggroup(
        help = hs(
            """Modify the %(progdesc)s configuration"""
        )
    )
    def config():
        pass

    if __name__ == '__main__':
        cli()

except KeyboardInterrupt:
    click.echo('Exited due to keyboard interrupt')
    sys.exit(130)
