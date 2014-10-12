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
import string


try: # py2
	letters = string.letters
except AttributeError: # py3
	letters = string.ascii_letters


def get_kernel_ng_conf_path(EPREFIX):
	return EPREFIX + '/etc/kernel-ng.conf'

#def write_make_conf(output, config_path, var, mirror_string):
#	"""Write the make.conf target changes
#
#	@param output: file, or output to print messages to
#	@param mirror_string: "var='hosts'" string to write
#	@param config_path; string
#	"""
#	output.write('\n')
#	output.print_info('Modifying %s with new mirrors...\n' % config_path)
#	try:
#		config = open(config_path, 'r')
#		output.write('\tReading make.conf\n')
#		lines = config.readlines()
#		config.close()
#		output.write('\tMoving to %s.backup\n' % config_path)
#		shutil.move(config_path, config_path + '.backup')
#	except IOError:
#		lines = []
#
#	regex = re.compile('^%s=.*' % var)
#	for line in lines:
#		if regex.match(line):
#			lines.remove(line)
#
#	lines.append(mirror_string)
#
#	output.write('\tWriting new %s\n' % config_path)
#
#	config = open(config_path, 'w')
#
#	for line in lines:
#		config.write(line)
#	config.write('\n')
#	config.close()
#
#	output.print_info('Done.\n')
#	sys.exit(0)
#
#
#def write_repos_conf(output, config_path, var, value):
#	"""Saves the new var value to a ConfigParser style file
#
#	@param output: file, or output to print messages to
#	@param config_path; string
#	@param var: string; the variable to save teh value to.
#	@param value: string, the value to set var to
#	"""
#	try:
#		from configparser import ConfigParser
#	except ImportError:
#		from ConfigParser import ConfigParser
#	config = ConfigParser()
#	config.read(config_path)
#	if config.has_option('gentoo', var):
#		config.set('gentoo', var, value)
#		with open(config_path, 'w') as configfile:
#			config.write(configfile)
#	else:
#		output.print_err("write_repos_conf(): Failed to find section 'gentoo',"
#			" variable: %s\nChanges NOT SAVED" %var)

