#!/usr/bin/env python
#-*- coding:utf-8 -*-
# vim:ai:sta:et:ts=4:sw=4:sts=4

"""Look, Ma!  No sources! 0.x
 Tool for selecting kernel options.

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

import os
import sys
from argparse import ArgumentParser, SUPPRESS
from lookmanosources.output import Output, ColoredFormatter
from lookmanosources.selectors import Interactive
from lookmanosources.configs import get_kernel_ng_conf_path
from lookmanosources.version import version

# eprefix compatibility
try:
    from portage.const import rootuid
except ImportError:
    rootuid = 0

# establish the eprefix, initially set so eprefixify can
# set it on install
EPREFIX = ""

# check and set it if it wasn't
if "GENTOO_PORTAGE_EPREFIX" in EPREFIX:
    EPREFIX = ''

class LookMaNoSources(object):
    '''Main operational class'''

    def __init__(self, output=None):
        '''LookMaNoSources class init

        @param output: lookmanosources.output.Ouptut() class instance
        or None for the default instance
        '''
        self.output = output or Output()

    @staticmethod
    def _have_bin(name):
        """Determines whether a particular binary is available
        on the host system.  It searches in the PATH environment
        variable paths.

        @param name: string, binary name to search for
        @rtype: string or None
        """
        for path_dir in os.environ.get("PATH", "").split(":"):
            if not path_dir:
                continue
            file_path = os.path.join(path_dir, name)
            if os.path.isfile(file_path) and os.access(file_path, os.X_OK):
                return file_path
        return None

    def change_config(self, features, out, config_path, sync=False):
        """Writes the config changes to the given file, or to stdout.

        @param features: list of host urls to write
        @param out: boolean, used to redirect output to stdout
        @param config_path; string
        """
        if hasattr(features[0], 'decode'):
            features = [x.decode('utf-8') for x in features]
        feature_string = 'features = "%s"' % ' '.join(features)

        if out:
            self.write_to_output(feature_string)
        else:
            write_kernel_ng_conf(self.output, config_path,
                'features', feature_string)

    @staticmethod
    def write_to_output(feature_string):
        print()
        print(feature_string)
        sys.exit(0)

    @property
    def progname(self):
        if sys.argv is None:
            return 'PROGRAM'
        return sys.argv[0].split(os.path.sep)[-1]

    def _parse_args(self, argv, config_path):
        """
        Does argument parsing and some sanity checks.
        Returns an optparse Options object.

        The descriptions, grouping, and possibly the amount sanity checking
        need some finishing touches.
        """
        p = ArgumentParser(prog=self.progname,
            description='A utility to maintain a site-specific overlay containing '
            'customized kernel-ng-based ebuilds.')
        p.add_argument( '--version', '-V', action='version',
            version='Look, Ma!  No sources!  Version: %s' % version)
        p.add_argument('--no-modify-overlay', '-w', help='Record the overlay in '
            'the configuration file as if it had been affected, but do not actually touch it.',
            action='store_false', dest='createoverlay')
        p.add_argument('-x', '--output', help='Treat configuration file as empty and '
            'output any modified configuration data to the specified file, or, the '
            'console, if not specified.', action='store', dest='output')
        p.add_argument('-c', '--crappy-terminal', help='Don\'t let ncurses make aggressive '
            'deductions about the functionality of the terminal -- assume it barely works '
            'for 7-bit ascii type stuff and that\'s it.', action='store_true',
            dest='crappyterminal')
        p.add_argument('-f', '--force', help=''.join(( 'Force creation of overlay even when',
            ' an unclean (i.e.: non-%(prog)s-generated) or non-overlay (i.e.: a regular file)',
            ' exists at the specified location' )), action='store_true', dest='force')

        psubs = p.add_subparsers(title='sub-commands', description='For sub-command help, '
            'issue %s <sub-command> -h' % self.progname, metavar='<sub-command>', help='overlay | "bust"')
        op = psubs.add_parser('overlay', help='Create, destroy and manipulate kernel-ng overlays')

        opsubs = op.add_subparsers(title='overlay sub-commands', description='For sub-command help, '
            'issue %s overlay <sub-command> -h' % self.progname, metavar='<sub-command>',
            help='create | destroy')
        opc = opsubs.add_parser('create', description='Creates an empty kernel-ng overlay '
            'in the filesystem and installs this overlay into the kernel-ng and portage '
            'configuration files.', help='Create a new kernel-ng overlay from scratch')

        vg_opc = opc.add_mutually_exclusive_group()
        vg_opc.add_argument('-v', '--verbose', help='verbosely explain what is happening and why.',
            action='store', type=int, default=2, dest='verbosity')
        vg_opc.add_argument('-q', '--quiet', help='Don\'t bother with informational messages.',
            action='store_const', const=0, dest='verbosity')

        opc.add_argument('-i', '--interactive', help='interactive mode: pause and allow '
            'user to override settings before acting', action='store_true', dest='runinteractively')

        rg_opc = opc.add_mutually_exclusive_group()
        rg_opc.add_argument('-1', '--no-save-config', help='Create the overlay but do not record '
            'its presence in the configuration files -- it only sits there on the filesystem.',
            action='store_false', dest='saveconfig')
        rg_opc.add_argument('-r', '--replace-overlay-config', help='If an overlay is already '
            'configured when the user requests a new overlay be created at a new location, '
            '%(prog)s will normally check whether the old overlay file-tree remains, and refuse '
            'to proceed if it does.  This argument prevents that check, allowing the user to '
            'configure kernel-ng to point to the new overlay without removing the old overlay '
            'files first', action='store_true', dest='replace_overlay_config')

        opc.add_argument('-o', '--overwrite', help='Overwrite any already existing overlay '
            'that may exist at the specified path.  If what is there does not appear to '
            'be an overlay, this will fail unless the --force options is used as well.',
            action='store_true', dest='ovloverwrite')
        opc.add_argument('-u', '--uid', help='UID of file owner of new overlay content',
            action='store', dest='ovluid', default=SUPPRESS)
        opc.add_argument('-g', '--gid', help='GID of group owner of new ovelay content',
            action='store', dest='ovlgid', default=SUPPRESS)
        opc.add_argument('-U', '--user', help='User-name of file-owner of new overlay content',
            action='store', dest='ovlusername', default=SUPPRESS)
        opc.add_argument('-G', '--group', help='Name of group-owner of new overlay content',
            action='store', dest='ovlgroupname', default=SUPPRESS)
        opc.add_argument('--no-group-write', help='Provision the new overlay with permissions '
            'matching \'chmod g-w\'.', action='store_false', dest='ovlgroupwritable')
        # implies 'no-group-write'
        opc.add_argument('--no-group-read', help='Provision the new overlay with permissions '
            'matching \'chmod og-r\'.  This implicitly activates the --no-group-write '
            'option as well.', action='store_false', dest='ovlgroupreadable')
        opc.add_argument('-p', '--path', help='filesystem path in which to create the overlay.  '
            'If not specified, the overlay path from the configuration file '
            'will be used, or, if none is configured, a default value of '
            '%s/usr/local/portage/ng-kernels will be used.' % EPREFIX, nargs=1,
            default=SUPPRESS, dest='path')
        opc.add_argument('name', help='Name of the new overlay to be created.  '
            'If the name is omitted on the command-line, %(prog)s will try first '
            'to find the setting from the global configuration file; if no such '
            'setting is specified, %(prog)s will default to "kernel-ng".',
            action='store', default=SUPPRESS, metavar='[ NAME ]')

        opd = opsubs.add_parser('destroy', description='Remove a kernel-ng overlay from the '
            'system.  This may come in handy when migrating away from a kernel-ng '
            'configuration (i.e, when reverting to gentoo-sources), or when moving the '
            'kernel-ng overlay around in the filesystem.  Also uninstalls '
            'the overlay from portage\'s repos.conf configuration file.',
            help='Remove and uninstall the kernel-ng overlay from the system.')

        vg_opd = opd.add_mutually_exclusive_group()
        vg_opd.add_argument('-v', '--verbose', help='verbosely explain what is happening and why.',
            action='store', type=int, default=2, dest='verbosity')
        vg_opd.add_argument('-q', '--quiet', help='Don\'t bother with informational messages.',
            action='store_const', const=0, dest='verbosity')

        opd.add_argument('-r', '--remove-overlay-config', help='if an overlay is already '
            'configured its settings are normally retained in the kernel-ng configuration '
            'files, with the result that subsequently creating a new overlay will default '
            'to using the same kernel-ng settings by default.  Issuing this command will cause '
            '%(prog)s to remove the overlay configuration, effectively resetting the entire '
            'system configuration to a vanilla state.', action='store_true', dest='remove_overlay_config')
        opd.add_argument('-p', '--path', help='filesystem path of the overlay to destroy.  '
            'If not specified, the overlay path from the configuration file will be used; '
            'otherwise, no action will be taken.', nargs=1, default=SUPPRESS, dest='path')
        opd.add_argument('name', help='The Gentoo repository (aka overlay) name of the overlay to be destroyed.  '
            'If not provided, either via the configured defaults or the command-line, the global default '
            'name of \'kernel-ng\' will be assumed.', action='store', default=SUPPRESS, metavar='[ NAME ]')

        if len(argv) == 1:
            p.print_help()
            sys.exit(1)

        options = p.parse_args()

        if (os.getuid() != rootuid) and not options.output:
            self.output.print_err('Must be root to write to %s!\n' % config_path)

        # return results
        return options

    def get_available_features(self, options):
        '''Returns a list of features suitable for consideration by a user
        based on user input

        @param options: p.parse_args() options instance
        @rtype: list
        '''
        # self.output.write("using features:\n" % FEATURES_XML, 2)
        features = [
            ('FooFeature', {'feature': 'foo', 'description': 'fooness'}),
            ('BarFeature', {'feature': 'bar', 'description': 'barness'}),
        ]
        return features

    def select_features(self, features, options):
        '''Returns the list of selected host urls using
        the options passed in interactive ncurses dialog

        @param hosts: list of features to choose from
        @param options: p.parse_args() options instance
        @rtype: list
        '''
        selector = Interactive(features, options, self.output)
        return selector.features

    def get_conf_path(self):
        '''Checks for the existance of repos.conf or make.conf in /etc/portage/
        Failing that it checks for it in /etc/
        Failing in /etc/ it defaults to /etc/portage/make.conf

        @rtype: string
        '''
        return get_kernel_ng_conf_path(EPREFIX)

    def main(self, argv):
        """Lets Rock!

        @param argv: list of command line arguments to parse
        """
        config_path = self.get_conf_path()
        options = self._parse_args(argv, config_path)
        self.output.verbosity = options.verbosity
        self.output.write("main(); config_path = %s\n" % config_path, 2)

        # reset config_path to find repos.conf/gentoo.conf if it exists
        config_path = self.get_conf_path()
        self.output.write("main(); reset config_path = %s\n" % config_path, 2)

        features = self.get_available_features(options)

        pickedfeatures = self.select_features(features, options)

        if len(pickedfeatures):
            self.change_config(pickedfeatures, options.output,
                config_path)
        else:
            self.output.write("No results found. "
                "Check your settings and re-run look-ma-no-sources.\n")
