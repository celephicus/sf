#!/usr/bin/env python3

# Testing out the intricacies of args with cmd2 using a toy standalone app.

from typing import Callable, Any, Tuple, List
import sys, cmd2

class NOTSET:
	"Don't make one of these!"
	def __eq__(self, other):
		return other is None
	def __repr__(self):
		return self.__class__.__name__

NOTSET = NOTSET()

assert NOTSET == None

def wrap_validator_or_none(validator):
	"Adds the facility to accept an empty string as None to a validator."
	return lambda a: None if not a else validator(a)

class ArgValidator:
  """Wrapper for a simple type that can wrap a simple type and validate the resulting conversion. """
  def __init__(self, t:type, validator:Callable[Any, Any]|None, name=None):
    self.t, self.validator = t, validator
    self.name = name or self.t.__name__
  def __repr__(self) -> str:
      """Will be printed as the 'argument type' to user on syntax or range error."""
      return f"{self.name}"
  def __call__(self, arg: str) -> Any:
    arg = self.t(arg)
    if not self.validator(arg):
      raise ValueError(f"validator error") # Value '{arg}': {self._get_validator_desc()}")
    return arg

PositiveInt = ArgValidator(int, lambda x: x>=0, "PositiveInt")
class SF_App(cmd2.Cmd):
	def __init__(self):
		super().__init__()

	def dump_args_option(self, args):
		self.poutput(f'Args: {", ".join([f"{k}={v}" for k,v in vars(args).items() if not k.startswith('cmd2')])}')

	foo_parser = cmd2.Cmd2ArgumentParser()
	foo_parser.add_argument("--foo", type=ArgValidator(int, lambda a: a>0), nargs='?', default=NOTSET)
	foo_parser.add_argument("--bar", type=PositiveInt, nargs='?', default=NOTSET)
	@cmd2.with_argparser(foo_parser)
	def do_foo(self, args):
		self.dump_args_option(args)
		self.poutput("Do foo.")

if __name__ == '__main__':
	sf_app = SF_App()
	sys.exit(sf_app.cmdloop())
