#!/usr/bin/env python3

import argparse

import cmd2
from cmd2 import (
    CommandSet,
    with_argparser,
    with_category,
    with_default_category,
)

@with_default_category("Fruits & vegetables")
class LoadableFruits(CommandSet):
    def __init__(self) -> None:
        """CommandSet class for dynamically loading commands related to fruits."""
        super().__init__()

    cut_parser = cmd2.Cmd2ArgumentParser()
    cut_subparsers = cut_parser.add_subparsers(title='item', help='item to cut')
    @with_argparser(cut_parser)
    def do_cut(self, ns: argparse.Namespace) -> None:
        handler = ns.cmd2_handler.get()
        if handler is not None:
            handler(ns)
        else:
            self.do_help('cut')


    base_parser = cmd2.Cmd2ArgumentParser(add_help=False)
    base_parser.add_argument("--foo")

    banana_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser], description="Cut a banana.")
    banana_parser.add_argument('direction', choices=['discs', 'lengthwise'], help="cutting action")

    @cmd2.as_subcommand_to('cut', 'banana', banana_parser, help=banana_parser.description)
    def cut_banana(self, ns: argparse.Namespace) -> None:
        """Cut banana."""
        self._cmd.poutput('cutting banana: ' + ns.direction)

    bokchoy_description = "Cut some bokchoy"
    bokchoy_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser], description=bokchoy_description)
    bokchoy_parser.add_argument('style', choices=['quartered', 'diced'])

    @cmd2.as_subcommand_to('cut', 'bokchoy', bokchoy_parser, help=bokchoy_description.lower())
    def cut_bokchoy(self, ns: argparse.Namespace) -> None:
        """Cut bokchoy."""
        self._cmd.poutput('Bok Choy: ' + ns.style)

class CommandSetApp(cmd2.Cmd):
    """CommandSets are automatically loaded. Nothing needs to be done."""

    def __init__(self) -> None:
        """Cmd2 application for demonstrating the CommandSet features."""
        # This prevents all CommandSets from auto-loading, which is necessary if you don't want some to load at startup
        super().__init__(auto_load_commands=True)

        self.intro = 'The CommandSet feature allows defining commands in multiple files and the dynamic load/unload at runtime'

if __name__ == '__main__':
    app = CommandSetApp()
    app.cmdloop()
