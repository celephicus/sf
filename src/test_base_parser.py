#!/usr/bin/env python3

from base_parser import *

import pytest

def test_NOTSET():
	assert NOTSET == None
	assert not NOTSET
	import copy
	v = NOTSET
	assert copy.copy(v) is v
	assert copy.deepcopy(v) is v

def test_argparse_exc():
	def foo(a, b=0):
		if b == 1:
			raise ValueError("ValueError raised")
		if b == -1:
			raise RuntimeError("RuntimeError raised")
		if b == 3:
			raise NameError("NameError raised")
		return a+b
	foo1 = argparse_exc(foo, ValueError)
	foo2 = argparse_exc(foo, (ValueError, RuntimeError))

	assert foo1(1) == 1
	assert foo1(1, 2) == 3

	with pytest.raises(argparse.ArgumentTypeError):
		foo1(0, 1)
	with pytest.raises(RuntimeError):
		foo1(0, -1)
	with pytest.raises(NameError):
		foo1(0, 3)

	with pytest.raises(argparse.ArgumentTypeError):
		foo2(0, 1)
	with pytest.raises(argparse.ArgumentTypeError):
		foo2(0, -1)
	with pytest.raises(NameError):
		foo1(0, 3)

'''
	assert as_argparse_exc(ValueError, foo, '1', '2') == '12'
	assert as_argparse_exc(ValueError, foo, '1', b='2') == '12'
	with pytest.raises(ValueError):
		foo('1', '3')
	with pytest.raises(argparse.ArgumentTypeError):
		as_argparse_exc(ValueError, foo, '1', '3')
	with pytest.raises(ValueError) as exc:
		as_argparse_exc(AttributeError, foo, '1', '3')
	print(exc, str(exc))
	assert "something broked" in str(exc)

'''

if __name__ == "__main__":
	parser = cmd2.Cmd2ArgumentParser(add_help=False, parents=[NODE_ATTRIBUTES])
	args = parser.parse_args()
	print(args)

	import copy
	v = [NOTSET]
	print(copy.deepcopy(v))
