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
    FRAMEWORK, SUBCONSTS, subconsts, EKERNELNG_CONF_DIR, KERNELNG_CONF_FILE, \
    KNGConfig

from ..output import trace, echov, sechov

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

    # nb: the indentation here must be kept synchronized with the indentation
    # in the click helpstrings below.
    SUBCMDHELP = \
            """
            The %(progname)s interface is broken into several nested
            subcommands.  For detailed subcommand help, issue the
            subcommand followed by the %(helpshort)s or %(helplong)s
            option, i.e.:

            \b
              # kernelng config -h""" % {
                'helpshort': click.style(HELPSHORT, fg='white', bold=True),
                'helplong': click.style(HELPLONG, fg='white', bold=True),
                'progname': click.style(PROGNAME, fg='white', bold=True)
            }

    CONFIG_EXAMPLE_OPTIONS = 'One, at most, of the %(i)s/%(install)s,' \
        ' %(I)s/%(install_as)s and %(a)s/%(append_to)s options may be used' \
        ' per invocation, as these each specify where the output goes.' % {
            'i': click.style('-i', fg='white', bold=True),
            'install': click.style('--install', fg='white', bold=True),
            'I': click.style('-I', fg='white', bold=True),
            'install_as': click.style('--install-as', fg='white', bold=True),
            'a': click.style('-a', fg='white', bold=True),
            'append_to': click.style('--append-to', fg='white', bold=True),
    }
    HS['progname'] = click.style(PROGNAME, fg='white', bold=True)
    HS['helpshort'] = HELPSHORT
    HS['helplong'] = HELPLONG
    HS['subcmdhelp'] = SUBCMDHELP
    HS['config_example_options'] = CONFIG_EXAMPLE_OPTIONS
    HS['fixme'] = click.style('>FIXME!<', fg='red', bold=True)

    HS['early_alpha_warning'] = ''.join((
        click.style('WARNING', fg='red', bold=True),
        click.style(':', fg='white', bold=True),
        ' ',
        click.style(PROGNAME, fg='magenta', bold=True),
        ' ',
        ' '.join((
            click.style(word, fg='magenta', bold=False) if word else word # ('')
            for word in ' '.join((
                'is in an early-alpha stage of development.  Many important',
                'features are as-yet unimplemented and the code is in a state',
                'of rapid flux.  It could easily break your ability to boot',
                'or worse.  Please keep an up-to-date backup, or gamble only',
                'with what you\'re fully prepared to lose.'
            )).split(' ')
        ))
    ))

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
            %(progdesc)s provides the %(progname)s command to manage
            a site-specific overlay containing customized portage packages
            utilizing the %(framework)s framework.  In other words, it
            facilitates the creation and installation of a fully deployed
            linux kernel package in Gentoo according to your preferences.

            %(early_alpha_warning)s

            From scratch, the following sequence of commands, run as root,
            would activate a generic %(framework)s configuration and
            generate the %(framework)s overlay:

            \b
              # %(prog)s config example --install
              # %(prog)s overlay create

            One could then issue the following to deploy the kernel
            from a %(framework)s overlay generated as above:

            \b
              # emerge sys-kernel/ng-sources

            Using an appropriate %(framework)s configuration for your site,
            there may be no need to run "genkernel," "make modules_install,"
            "grub2-mkconfig," nor any other kernel-specific installation
            ritual.  Instead, your kernel may be managed just like the other
            packages on your Gentoo or Gentoo-like system, using portage.

            There is, however, one extra bit of labor that must be regularly
            performed to update the %(framework)s overlay with ebuilds
            corresponding to the latest-and-greatest kernel packages available
            in Gentoo.  Someone must run:

            \b
              # %(prog)s overlay update

            Those comfortable automating their kernel upgrade process
            entirely could integrate this step into their standard emerge
            --sync process by %(fixme)sing.

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
    @trace
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
    @trace
    def create(uid, gid, perm):
        if uid == -1:
            # these int casts resolve the portage proxies into integers and
            # are required in recent python3's
            uid = int(portage_uid)
            gid = int(portage_gid)
        conf = KNGConfig()
        # conf.loadConfigText(config_file)
        # if location is not None:
        #     conf.globals['overlay'].override = location
        # if conf.overlayExists():
        #     if not force:
        #         conf.destroyOverlay()
        conf.createOverlay(uid, gid, perm)

    @overlay.kngcommand(
        help = hs(
            """
            Deactivates and/or removes the %(progdesc)s overlay.
            """
        ),
        short_help = hs("Deactivate or remove %(progdesc)s overlay.")
    )
    @trace
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
    @trace
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
    @trace
    def show():
        pass

    @config.kngcommand(
        help = hs(
            """
            Display or save the hard-coded example configuration file that came with this version of %(progdesc)s.
            The output is in the "%(kngconf)s" format utilized by %(progname)s, and illustrates the %(kngconf)s
            syntax while providing a brief commented explanation of each of the supported settings.  The example
            may also serve as a means to bootstrap the %(progdesc)s configuration process, as it contains a sensible
            baseline configuration likely to meet the needs of a plurality of %(framework)s users.

            %(config_example_options)s
            """
        ),
        short_help = hs("Display or save the example configuration file.")
    )
    @click.option('-i', '--install', is_flag=True, help=hs('Bootstrap the %(framework)s configuration process by saving the '
        'configuration example file to %(kngconffile)s.'))
    @click.option('-I', '--install-as', type=click.Path(dir_okay=False, writable=True), help='Write output to file instead of standard output.')
    @click.option('-a', '--append-to', type=click.Path(dir_okay=False, writable=True), help='Append output to end of the specified file.')
    @click.option('-f', '--force', is_flag=True, help='Replace existing configuration file, if present (applies to %s and %s options).' % (
        click.style('--install-as', fg='white', bold=True), click.style('--install', fg='white', bold=True)))
    @click.option('-n', '--no-comments', is_flag=True, help='Omit all comments and blank lines in the example file.')
    @trace
    def example(install=None, install_as=None, append_to=None, force=False, no_comments=False):
        outfile = None
        s=sum([1 if x else 0 for x in [install, install_as, append_to]])
        if s > 1:
            raise click.UsageError('-i/--install, -I/--install-as, and -a/--append-to arguments applied simultaneously.')
        if force and (not (install or install_as)):
            raise click.UsageError('--force only relevant to -i/--install or -I/--install-as options')

        filename = KERNELNG_CONF_FILE if install \
            else install_as if install_as \
            else append_to if append_to \
            else None

        conf = KNGConfig()
        conf.loadExampleConfig()

        if filename:
            mode='a' if append_to \
                else 'w' if force \
                else 'x'
            if os.path.exists(filename):
                if os.path.isdir(filename):
                    raise click.ClickException('%s must not be a directory.' % filename)
                elif (not append_to) and not force:
                    raise click.ClickException('File %s already exists but --force option not provided.' % filename)
            dirname = os.path.dirname(filename)
            basename = os.path.basename(filename)
            if not basename:
                raise click.ClickException('filename %s appears to be an invalid file-name.' % filename)
            elif not os.path.exists(dirname):
                os.makedirs(os.path.dirname(filename))
            elif not os.path.isdir(dirname):
                raise click.ClickException('Whatever %s is, it\'s not the directory we need to store %s in.' % (dirname, filename))
            else:
                with click.open_file(filename, mode=mode) as outfile:
                    conf.writeConfigText(file=outfile, no_comments=no_comments)
        else:
            conf.writeConfigText(no_comments=no_comments)

    if __name__ == '__main__':
        cli()

except KeyboardInterrupt:
    click.echo('Exited due to keyboard interrupt')
    sys.exit(130)
