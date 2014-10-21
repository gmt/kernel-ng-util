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

from contextlib import contextmanager

from click.core import Context, Command, Group
from click.termui import style, get_terminal_size
from click.formatting import HelpFormatter
from click.decorators import command, option, version_option
import click

from .kngclicktextwrapper import KNGClickTextWrapper
from .kngtextwrapper import kngterm_len, kngexpandtabs
from .version import version

KNG_OPTIONS_METAVAR = ''.join((
    style('[', fg='blue'),
    style('OPTIONS', fg='cyan', bold=True),
    style(']', fg='blue')))

SUBCOMMAND_METAVAR = ''.join((
    style('COMMAND', fg='cyan', bold=True),
    ' ',
    style('[', fg='blue'),
    style('ARGS', fg='cyan', bold=True),
    style(']...', fg='blue')))

SUBCOMMANDS_METAVAR = ''.join((
    style('COMMAND1', fg='cyan', bold=True),
    ' ',
    style('[', fg='blue'),
    style('ARGS', fg='cyan', bold=True),
    style(']...', fg='blue'),
    ' ',
    style('[', fg='blue'),
    style('COMMAND2', fg='cyan', bold=True),
    ' ',
    style('[', fg='blue'),
    style('ARGS', fg='cyan', bold=True),
    style(']...', fg='blue'),
    style(']...', fg='blue')))

NOCOLORIZEHELP = "Do not colorize output or use advanced terminal features."

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

click.formatting.__dict__['wrap_text'] = kngwrap_text

class KNGHelpFormatter(HelpFormatter):
    # allow a maximum default width of 120 vs. HelpFormatter's 80
    def __init__(self, *args, **kwargs):
        if 'width' in kwargs:
            width = kwargs.pop('width')
        else:
            width = None
        width = max(min(get_terminal_size()[0], 120) - 2, 50) if width is None else width
        kwargs['width'] = width
        self._kngsection = None
        super(KNGHelpFormatter, self).__init__(*args, **kwargs)

    @contextmanager
    def section(self, name):
        """Wrap click.HelpFormatter.section() so as to track the
        most recently added section name.

        :param name: the section name to pass to click.HelpFormatter.section()
        """
        with super(KNGHelpFormatter, self).section(name):
            oldkngsection = self._kngsection
            self._kngsection = name
            try:
                print('KNGHelpFormatter.section: %s -> %s' % (oldkngsection, name))
                yield
            finally:
                self._kngsection = oldkngsection

    def write_usage(self, prog, args='', prefix='Usage: '):
        prog = style(prog, fg='white', bold=True)
        super(KNGHelpFormatter, self).write_usage(prog, args=args, prefix=prefix)

    def dl_style_word(self, word):
        if len(word) == 0:
            return word
        elif word[:1] == '-':
            return style(word, fg='white', bold=True)
        elif self._kngsection == 'Options':
            # for the options definiton list, we make non-hyphenated
            # words yellow; otherwise, we stick to white
            print('dl_style_word: %s(%s)' % (self._kngsection, word))
            return style(word, fg='yellow', bold=True)
        else:
            print('dl_style_word: %s(%s)' % (self._kngsection, word))
            return style(word, fg='white', bold=True)

    def write_dl(self, rows, *args, **kwargs):
        newrows = []
        for row in rows:
            if len(row) != 2:
                raise TypeError('Expected two columns for definition list')
            newrows.append((
                ','.join((
                    ' '.join((
                        self.dl_style_word(spacesepstr) for spacesepstr in commasepstr.split(' ')
                    )) for commasepstr in row[0].split(',')
                )),
                row[1]
            ))
        super(KNGHelpFormatter, self).write_dl(newrows, *args, **kwargs)

class KNGContext(Context):
    def make_formatter(self):
        return KNGHelpFormatter(width=self.terminal_width)

no_color_mode = False

# generate a new echo function suitable for monkey patching an old one
def nocolorecho(oldecho):
    def newecho(*args, **kwargs):
        if no_color_mode:
            if len(args) > 0:
                args=(click._compat.strip_ansi(args[0]),) + args[1:]
            else:
                message = kwargs.pop('message', None)
                if message is not None:
                    kwargs['message'] = click._compat.strip_ansi(message)
        oldecho(*args, **kwargs)
    return newecho

# monkey patch click's echo functions to always ignore color, regardless
# of the output's isatty-ness when no_color_mode is True -- but only
# bother if no_color_mode is, indeed, true, and we haven't already
# monkey patched it.
def no_color(ctx, command, value):
    global no_color_mode
    oldval = no_color_mode
    no_color_mode = no_color_mode or value
    if (not oldval) and no_color_mode:
        click.utils.__dict__['echo'] = nocolorecho(click.utils.echo)
        click.core.__dict__['echo'] = nocolorecho(click.core.echo)
        click.__dict__['echo'] = nocolorecho(click.echo)

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


def kngcommandcommon(name=None, cls=None, **kwargs):
    '''
    Invoke the click.command decorator with additional decorations common
    to all commands and groups in the kernel-ng-utils command-line framework.
    Routing through this instead of click.command allows users to place the
    options provided by the additional decorations freely within the kernelng
    command-line, so, for example, kernelng -C foo bar, kernelng foo -C bar,
    and kernelng foo bar -C all do the expected thing.  The additional
    decorations hard-code (along with their implementations) the following
    options::

      -C, --no-color: suppresses fancy terminal behavior
      -V, --version: dump version info & terminate
    '''
    def decorator(f):
        return version_option(version, '-V', '--version')(
            option('-C', '--no-color', is_flag=True, callback=no_color,
                default=False, is_eager=True, expose_value=False, help=NOCOLORIZEHELP)(
                   command(name, cls, **kwargs)(f)))
    return decorator

def kngcommand(name=None, cls=None, **kwargs):
    cls = KNGCommand if cls is None else cls
    return kngcommandcommon(name, cls, **kwargs)

def knggroup(name=None, cls=None, **kwargs):
    cls = KNGGroup if cls is None else cls
    return kngcommandcommon(name, cls, **kwargs)
