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
from kernelng.kngclick import kngcommand, knggroup, OCTAL_3

import portage

from ..config import EPREFIX, portage_uid, portage_gid, PROGNAME, PROGDESC, \
    FRAMEWORK, SUBCONSTS, subconsts, EKERNELNG_CONF_DIR, KERNELNG_CONF_FILE

from ..output import auto_trace_function, auto_trace_method, echov, sechov

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

    # augment the general substitution constants dict with command-line
    # specific constants

    HS = SUBCONSTS.copy()
    HELPSHORT = '-h'
    HELPLONG = '--help'
    SUBCMDHELP = 'For detailed help with subcommands, issue the subcommand' \
        ' followed by the %(helpshort)s or %(helplong)s option.' % {
            'helpshort': click.style(HELPSHORT, fg='white', bold=True),
            'helplong': click.style(HELPLONG, fg='white', bold=True),
    }
    CONFIG_EXAMPLE_OPTIONS = 'One, at most, of the %(o)s/%(output_to)s,' \
        ' %(a)s/%(append_to)s or %(f)s/%(force)s options may be used' \
        ' per invocation, as each specifies where the output goes.' % {
            'o': click.style('-o', fg='white', bold=True),
            'output_to': click.style('--output-to', fg='white', bold=True),
            'a': click.style('-a', fg='white', bold=True),
            'append_to': click.style('--append-to', fg='white', bold=True),
            'f': click.style('-f', fg='white', bold=True),
            'force': click.style('--force', fg='white', bold=True),
    }
    HS['progname'] = click.style(PROGNAME, fg='white', bold=True)
    HS['helpshort'] = HELPSHORT
    HS['helplong'] = HELPLONG
    HS['subcmdhelp'] = SUBCMDHELP
    HS['config_example_options'] = CONFIG_EXAMPLE_OPTIONS

    def hs(value):
        return subconsts(value, subconsts=HS)

    CONTEXT_SETTINGS = dict(
        help_option_names = [HELPSHORT, HELPLONG]
    )

    @knggroup(
        PROGNAME,
        context_settings=CONTEXT_SETTINGS,
        help = hs(
            """
            %(progdesc)s provides the %(prog)s command to manage
            a site-specific overlay containing customized %(framework)s
            packages.  The following example sequence
            of commands could be used to configure and deploy
            a %(framework)s package from scratch:

            \b
              $ sudo %(prog)s config example --force
              $ sudo %(prog)s overlay create
              $ sudo %(prog)s ebuild create ng
              $ sudo emerge -u @world

            %(subcmdhelp)s
            """
        )
    )
    def cli():
        pass

    @cli.knggroup(
        help = hs(
            """
            Manage the %(progdesc)s overlay.

            %(subcmdhelp)s
            """
        )
    )
    @auto_trace_function
    def overlay():
        pass

    @overlay.kngcommand(
        help = hs(
            """
            Creates and activates an empty %(progdesc)s overlay.
            """
        ),
        short_help = hs("Create and activate an empty %(progdesc)s overlay.")
    )
    @click.option('-u', '--uid', type=click.INT, default=-1,
        help='Numeric user id to assign to overlay files.')
    @click.option('-g', '--gid', type=click.INT, default=-1,
        help='Numeric group id to assign to overlay files.')
    @click.option('-p', '--perm', type=OCTAL_3, default=0o664,
        help='Three-digit octal permissions to assign to overlay files.')
    @auto_trace_function
    def create(uid, gid, perm):
        if uid == -1:
            # these int casts resolve the portage proxies into integers and
            # are required in recent python3's
            uid = int(portage_uid)
            gid = int(portage_gid)
        pass

    @overlay.kngcommand(
        help = hs(
            """
            Deactivates and/or removes the %(progdesc)s overlay.
            """
        ),
        short_help = hs("Deactivate or remove %(progdesc)s overlay.")
    )
    @auto_trace_function
    def destroy():
        pass

    @cli.knggroup(
        help = hs(
            """
            Modify the %(progdesc)s configuration.

            %(subcmdhelp)s
            """
        )
    )
    @auto_trace_function
    def config():
        pass

    @config.knggroup(
        help = hs(
            """
            Display %(framework)s actual or default configuration information.
            """
        ),
        short_help = hs("Display %(framework)s configuration info.")
    )
    @auto_trace_function
    def show():
        pass

    @config.kngcommand(
        help = hs(
            """
            Display the hard-coded example %(framework)s configuration file which shipped with this version of %(progname)s.

            %(config_example_options)s
            """
        ),
        short_help = hs("Display an example configuration file.")
    )
    @click.option('-o', '--output-to', type=click.File('w'), help='Write output to file instead of standard output.')
    @click.option('-a', '--append-to', type=click.File('a'), help='Append output to end of file.')
    @click.option('-f', '--force', is_flag=True, help='Reset global configuration file to contain the example config.')
    @auto_trace_function
    def example(output_to=None, append_to=None, force=False):
        outfile = None
        if sum([1 if x else 0 for x in [output_to, append_to, force]]) > 1:
            raise click.UsageError('Cannot supply -o/--output-to, -a/--append-to, or -f/--force arguments simultaneously.')
        if output_to:
            outfile = output_to
        elif append_to:
            outfile = append_to
        elif force:
            if not os.path.exists(EKERNELNG_CONF_DIR):
                os.makedirs(EKERNELNG_CONF_DIR)
            outfile = click.open_file(KERNELNG_CONF_FILE, 'w')
        try:
            from ..config import KNGConfig
            conf = KNGConfig()
            conf.loadExampleConfig()
            conf.writeConfigText(file=outfile)
        finally:
            if force:
                outfile.close()

    if __name__ == '__main__':
        cli()

except KeyboardInterrupt:
    click.echo('Exited due to keyboard interrupt')
    sys.exit(130)
