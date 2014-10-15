#!/usr/bin/env python
# coding: utf-8
# vim:ai:sta:et:ts=4:sw=4:sts=4

from __future__ import print_function

import re
import sys
from setuptools import setup, Command
from distutils import log

import os
import io
import re

__version__ = os.getenv('VERSION', default=os.getenv('PVR', default='9999'))

cwd = os.getcwd()

# establish the eprefix, initially set so eprefixify can
# set it on install
EPREFIX = "@GENTOO_PORTAGE_EPREFIX@"

# check and set it if it wasn't
if "GENTOO_PORTAGE_EPREFIX" in EPREFIX:
    EPREFIX = ''

# Python files that need `version = ""` subbed, relative to this dir:
python_scripts = [os.path.join(cwd, path) for path in (
    'kernelng/version.py',
)]

manpage = [os.path.join(cwd, path) for path in (
    'kernelng.8',
)]

class set_version(Command):
    """Set python version to our __version__."""
    description = "hardcode scripts' version using VERSION from environment"
    user_options = []  # [(long_name, short_name, desc),]

    def initialize_options (self):
        pass
    def finalize_options (self):
        pass
    def run(self):
        ver = 'git' if __version__ == '9999' else __version__
        print("Setting version to %s" % ver)

        def sub(files, pattern):
            for f in files:
                updated_file = []
                with io.open(f, 'r', 1, 'utf_8') as s:
                    for line in s:
                        newline = re.sub(pattern, '"%s"' % ver, line, 1)
                        if newline != line:
                            log.info("%s: %s" % (f, newline))
                        updated_file.append(newline)
                with io.open(f, 'w', 1, 'utf_8') as s:
                    s.writelines(updated_file)

        quote = r'[\'"]{1}'
        python_re = r'(?<=^version = )' + quote + '[^\'"]*' + quote
        sub(python_scripts, python_re)
        man_re = r'(?<=^.TH "kernelng" "8" )' + quote + '[^\'"]*' + quote
        sub(manpage, man_re)

def load_test():
    """Only return the real test class if it's actually being run so that we
    don't depend on snakeoil just to install."""

    desc = "run the test suite"
    if 'test' in sys.argv[1:]:
        try:
            from snakeoil import distutils_extensions
        except ImportError:
            sys.stderr.write("Error: We depend on dev-python/snakeoil ")
            sys.stderr.write("to run tests.\n")
            sys.exit(1)
        class test(distutils_extensions.test):
            description = desc
            default_test_namespace = 'kernelng.test'
    else:
        class test(Command):
            description = desc

    return test

test_data = {
    'kernelng': [
    ]
}

setup(
    name='kernelng',
    version=__version__,
    description='Tool for maintaining site-specific Gentoo overlays of customized kernel-ng ebuilds.',
    author='Gregory M. Turner',
    author_email='gmt@be-evil.net',
    maintainer='Gregory M. Turner',
    maintainer_email='gmt@be-evil.net',
    url='https://github.com/gmt/kernel-ng-util',
    download_url='https://github.com/gmt/kernel-ng-util/releases/downloads/v%(pv)s/kernel-ng-util-%(pv)s.tar.gz' \
        % {'pv': re.sub(r'-r[[:digit:]]*$', r'', __version__)},
    packages=['kernelng'],
    #package_data = test_data,
    data_files=(
        (os.path.join(os.sep, EPREFIX.lstrip(os.sep), 'usr/share/man/man8'), ['kernelng.8']),
    ),
    cmdclass={
        'test': load_test(),
        'set_version': set_version,
    },
    install_requires=[
        'Click'
    ],
    entry_points='''
        [console_scripts]
        kernelng=kernelng.scripts.kernelng:cli
    ''',
)
