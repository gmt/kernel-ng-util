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

import signal
import sys
import hashlib
import subprocess

from lookmanosources.output import encoder, get_encoding, decode_selection

class Interactive(object):
    """Handles interactive features selection."""

    def __init__(self, features, options, output):
        self.output = output
        self.features = []

        self.interactive(features, options)
        self.output.write('Interactive.interactive(): self.features = %s\n'
            % self.features, 2)

        if not self.features or len(self.features[0]) == 0:
            sys.exit(1)

    def interactive(self, features, options):
        """
        Some sort of interactive menu thingy.
        """
        dialog = ['dialog', '--separate-output', '--stdout', '--title',
            '"Select kernel feature sets:"', '--checklist',
            '"Please select your desired features:']
        dialog.extend(['20', '110', '14'])
        for (feature, args) in sorted(features, key = lambda x: x[1]['feature'].lower()):
            dialog.extend([ "%s" % feature, "%s" % args['description'], "OFF" ])
        dialog = [encoder(x, get_encoding(sys.stdout)) for x in dialog]
        proc = subprocess.Popen( dialog,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        out, err = proc.communicate()

        self.features = out.splitlines()

        if self.features:
            if hasattr(self.features[0], 'decode'):
                self.features = decode_selection(
                    [x.decode('utf-8').rstrip() for x in self.features])
            else:
                self.features= decode_selection([x.rstrip() for x in self.features])
