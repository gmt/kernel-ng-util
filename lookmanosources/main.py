#!/usr/bin/env python
#-*- coding:utf-8 -*-

"""Look, Ma!  No sources! 0.x
 Tool for selecting kernel options.

Copyright 2014 Gentoo Foundation

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
from optparse import OptionParser
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

		feature_string = 'features = "%s"' % (var, ' '.join(features))

		if out:
			self.write_to_output(feature_string)
		else:
			write_kernel_ng_conf(self.output, config_path, var, feature_string)


	@staticmethod
	def write_to_output(feature_string):
		print()
		print(feature_string)
		sys.exit(0)


	def _parse_args(self, argv, config_path):
		"""
		Does argument parsing and some sanity checks.
		Returns an optparse Options object.

		The descriptions, grouping, and possibly the amount sanity checking
		need some finishing touches.
		"""
		desc = "\n".join((
			self.output.white("examples:"),
			"",
			self.output.white("	 automatic:"),
			"		 # look-ma-no-sources -foo",
			"		 # look-ma-no-sources --bar --baz >> /mnt/gentoo/etc/kernel-ng/kernel-ng.conf",
			"",
			self.output.white("	 interactive:"),
			"		 # look-ma-no-sources -i",
			))
		parser = OptionParser(
			formatter=ColoredFormatter(self.output), description=desc,
			version='Look, Ma!  No sources!  version: %s' % version)

		group = parser.add_option_group("Main modes")
		group.add_option(
			"-i", "--interactive", action="store_true", default=False,
			help="Interactive Mode, this will present a list "
			"to make it possible to select mirrors you wish to use.")

		group = parser.add_option_group("Other options")
		group.add_option(
			"-d", "--debug", action="store", type="int", dest="verbosity",
			default=1, help="debug mode, pass in the debug level [1-9]")
		group.add_option(
			"-f", "--file", action="store", default='mirrorselect-test',
			help="An alternate file to download for deep testing. "
				"Please choose the file carefully as to not abuse the system "
				"by selecting an overly large size file.  You must also "
				" use the -m, --md5 option.")
		group.add_option(
			"-o", "--output", action="store_true", default=False,
			help="Output Only Mode, this is especially useful "
			"when being used during installation, to redirect "
			"output to a file other than %s" % config_path)
		group.add_option(
			"-q", "--quiet", action="store_const", const=0, dest="verbosity",
			help="Quiet mode")


		if len(argv) == 1:
			parser.print_help()
			sys.exit(1)

		options, args = parser.parse_args(argv[1:])

		# sanity checks

		# hack: check if more than one of these is set

		if (os.getuid() != rootuid) and not options.output:
			self.output.print_err('Must be root to write to %s!\n' % config_path)

		if args:
			self.output.print_err('Unexpected arguments passed.')

		# return results
		return options


	def get_available_features(self, options):
		'''Returns a list of features suitable for consideration by a user
		based on user input

		@param options: parser.parse_args() options instance
		@rtype: list
		'''
		# self.output.write("using features:\n" % FEATURES_XML, 2)
                features = [ {'name': 'foo', 'description': 'fooness'},
                             {'name': 'bar', 'description': 'barness'} ]
		return features


	def select_features(self, features, options):
		'''Returns the list of selected host urls using
		the options passed in interactive ncurses dialog

		@param hosts: list of features to choose from
		@param options: parser.parse_args() options instance
		@rtype: list
		'''
		selector = Interactive(features, options, self.output)
		return selector.urls


	def get_conf_path(self, rsync=False):
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
		config_path = self.get_conf_path(options.rsync)
		self.output.write("main(); reset config_path = %s\n" % config_path, 2)

		features = self.get_available_features(options)

		pickedfeatures = self.select_features(features, options)

		if len(pickedfeatures):
			self.change_config(pickedfeatures, options.output,
				config_path)
		else:
			self.output.write("No results found. "
				"Check your settings and re-run look-ma-no-sources.\n")
