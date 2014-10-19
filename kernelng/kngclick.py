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
        Copyright (C) 2014 by Armin Ronacher
        Copyright (C) 2014 Gregory M. Turner <gmt@be-evil.net>

Due to interface limitations, portions of this code had to
 be cut-pasted from Armin Ronacher's click framework, which, for now, has
 a more liberal license than that of kernel-ng-util.  Armin's code
 is BSD licensed: see https://github.com/mitsuhiko/click/blob/master/LICENSE
 for the gory details.

Feel free to treat everything in this file under the terms of that
 license. Note: when and if he can get all of the mirror-select-isms out of
 kernel-ng-util, Greg may attempt to relicense everything along similar
 lines, so as to clear up any license-soup problems this creates.
"""

from __future__ import print_function

from click.core import Context, Command, Group
from click.termui import style
from click.formatting import HelpFormatter
from click.decorators import command

from .kngclicktextwrapper import KNGClickTextWrapper
from .kngtextwrapper import kngterm_len, kngexpandtabs

KNG_OPTIONS_METAVAR = ''.join((
    style('[', fg='blue'),
    style('OPTIONS', fg='magenta', bold=True),
    style(']', fg='blue')))

SUBCOMMAND_METAVAR = ''.join((
    style('COMMAND', fg='magenta', bold=True),
    ' ',
    style('[', fg='blue'),
    style('ARGS', fg='magenta', bold=True),
    style(']...', fg='blue')))

SUBCOMMANDS_METAVAR = ''.join((
    style('COMMAND1', fg='magenta', bold=True),
    ' ',
    style('[', fg='blue'),
    style('ARGS', fg='magenta', bold=True),
    style(']...', fg='blue'),
    ' ',
    style('[', fg='blue'),
    style('COMMAND2', fg='magenta', bold=True),
    ' ',
    style('[', fg='blue'),
    style('ARGS', fg='magenta', bold=True),
    style(']...', fg='blue'),
    style(']...', fg='blue')))

def kngwrap_text(text, width=78, initial_indent='', subsequent_indent='',
              preserve_paragraphs=False):
    """A helper function that intelligently wraps text.  By default, it
    assumes that it operates on a single paragraph of text but if the
    `preserve_paragraphs` parameter is provided it will intelligently
    handle paragraphs (defined by two empty lines).

    If paragraphs are handled, a paragraph can be prefixed with an empty
    line containing the ``\\b`` character (``\\x08``) to indicate that
    no rewrapping should happen in that block.

    :param text: the text that should be rewrapped.
    :param width: the maximum width for the text.
    :param initial_indent: the initial indent that should be placed on the
                           first line as a string.
    :param subsequent_indent: the indent string that should be placed on
                              each consecutive line.
    :param preserve_paragraphs: if this flag is set then the wrapping will
                                intelligently handle paragraphs.
    """
    text = kngexpandtabs(text)
    wrapper = KNGClickTextWrapper(width, initial_indent=initial_indent,
                          subsequent_indent=subsequent_indent,
                          replace_whitespace=False)
    if not preserve_paragraphs:
        return wrapper.fill(text)

    p = []
    buf = []
    indent = None

    def _flush_par():
        if not buf:
            return
        if buf[0].strip() == '\b':
            p.append((indent or 0, True, '\n'.join(buf[1:])))
        else:
            p.append((indent or 0, False, ' '.join(buf)))
        del buf[:]

    for line in text.splitlines():
        if not line:
            _flush_par()
            indent = None
        else:
            if indent is None:
                orig_len = kngterm_len(line)
                line = line.lstrip()
                indent = orig_len - kngterm_len(line)
            buf.append(line)
    _flush_par()

    rv = []
    for indent, raw, text in p:
        with wrapper.extra_indent(' ' * indent):
            if raw:
                rv.append(wrapper.indent_only(text))
            else:
                rv.append(wrapper.fill(text))

    return '\n\n'.join(rv)


class KNGHelpFormatter(HelpFormatter):
    def write_usage(self, prog, args='', prefix='Usage: '):
        """Writes a usage line into the buffer.

        :param prog: the program name.
        :param args: whitespace separated list of arguments.
        :param prefix: the prefix for the first line.
        """
        prog = style(prog, fg='white', bold=True)

        prefix = '%*s%s' % (self.current_indent, prefix, prog)
        self.write(prefix)

        ptl = kngterm_len(prefix)
        text_width = max(self.width - self.current_indent - ptl, 10)
        indent = ' ' * (ptl + 1)

        self.write(kngwrap_text(args, text_width,
                             initial_indent=' ',
                             subsequent_indent=indent))
        self.write('\n')

class KNGContext(Context):
    def make_formatter(self):
        return KNGHelpFormatter(width=self.terminal_width)

class KNGGroup(Group):
    def __init__(self, *args, **kwargs):
        options_metavar = kwargs.pop('options_metavar', KNG_OPTIONS_METAVAR)
        kwargs['options_metavar'] = options_metavar
        chain=kwargs.pop('chain', False)
        kwargs['chain'] = chain
        subcommand_metavar = kwargs.pop('subcommand_metavar',
            SUBCOMMANDS_METAVAR if chain else SUBCOMMAND_METAVAR)
        kwargs['subcommand_metavar'] = subcommand_metavar
        super(KNGGroup, self).__init__(*args, **kwargs)
    def make_context(self, info_name, args, parent=None, **extra):
        for key, value in iter((self.context_settings or {}).items()):
            if key not in extra:
                extra[key] = value
        ctx = KNGContext(self, info_name=info_name, parent=parent, **extra)
        self.parse_args(ctx, args)
        return ctx
    def kngcommand(self, *args, **kwargs):
        def decorator(f):
            cmd = kngcommand(*args, **kwargs)(f)
            self.add_command(cmd)
            return cmd
        return decorator
    def knggroup(self, *args, **kwargs):
        def decorator(f):
            cmd = knggroup(*args, **kwargs)(f)
            self.add_command(cmd)
            return cmd
        return decorator

class KNGCommand(Command):
    def __init__(self, *args, **kwargs):
        options_metavar = kwargs.pop('options_metavar', KNG_OPTIONS_METAVAR)
        kwargs['options_metavar'] = options_metavar
        super(KNGCommand, self).__init__(*args, **kwargs)
    def make_context(self, info_name, args, parent=None, **extra):
        for key, value in iter((self.context_settings or {}).items()):
            if key not in extra:
                extra[key] = value
        ctx = KNGContext(self, info_name=info_name, parent=parent, **extra)
        self.parse_args(ctx, args)
        return ctx
    def kngcommand(self, *args, **kwargs):
        def decorator(f):
            cmd = kngcommand(*args, **kwargs)(f)
            self.add_command(cmd)
            return cmd
        return decorator
    def knggroup(self, *args, **kwargs):
        def decorator(f):
            cmd = knggroup(*args, **kwargs)(f)
            self.add_command(cmd)
            return cmd
        return decorator

def kngcommand(name=None, **kwargs):
    kwargs.setdefault('cls', KNGCommand)
    return command(name, **kwargs)

def knggroup(name=None, **kwargs):
    kwargs.setdefault('cls', KNGGroup)
    return command(name, **kwargs)

