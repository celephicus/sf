#!/usr/bin/env python3

# Testing out the intricacies of args with cmd2 using a toy standalone app.

from typing import Callable, Any, Tuple, List
import sys, cmd2

import utils, base_parser

PositiveInt = utils.ArgValidator(int, lambda x: x>=0, "PositiveInt")
class SF_App(cmd2.Cmd):
	def __init__(self):
		super().__init__()

	def dump_args_option(self, args):
		self.poutput(utils.dump_custom_options(args))

	foo_parser = cmd2.Cmd2ArgumentParser()
	foo_parser.add_argument("--foo", type=utils.ArgValidator(int, lambda a: a>0), nargs='?', default=base_parser.NOTSET)
	foo_parser.add_argument("--bar", type=PositiveInt, nargs='?', default=base_parser.NOTSET)
	@cmd2.with_argparser(foo_parser)
	def do_foo(self, args):
		self.dump_args_option(args)
		self.poutput("Do foo.")

if __name__ == '__main__':
	sf_app = SF_App()
	sys.exit(sf_app.cmdloop())
