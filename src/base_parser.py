import argparse, copy
from typing import Callable, Any, Tuple, List

import cmd2

import utils
from layer_set import LayerSet

class _NOTSET:
	"""Default value for attribute args so that we can purposely set them to None. Don't make one of these!
		Note override for deepcopy & copy, else copy.copy() & copy.deepcopy() create new objects!"""
	def __deepcopy__(self, memo):
		return self           # Why is this missing from examples?
	def __copy__(self):
		return self
	def __eq__(self, other):
		return other is None
	def __bool__(self):
		return False
	def __repr__(self):
		return "NOTSET"

# There shalll be one and only one!
NOTSET = _NOTSET()
del _NOTSET
# We need a lot of parsers. So we make a few base parsers and inherit from them as needed.

# Base parser for all utility commands. it just takes a number of layers as positional arguments.
MULTI_INPUT_LAYERS_PARSER = cmd2.Cmd2ArgumentParser(add_help=False)
MULTI_INPUT_LAYERS_PARSER.add_argument("layers", type=str, nargs='*',
	help="Multiple layers with data to process, or blank for all.")

# Base parser with generic layer attributes.
GENERIC_ATTRIBUTES_PARSER = cmd2.Cmd2ArgumentParser(add_help=False)
GENERIC_ATTRIBUTES_PARSER.add_argument("--colour", '-C', type=utils.Colour, nargs='?', default=NOTSET,
	help="Set line colour attribute, use #rrggbb or html colour names. Maps to 'stroke' in SVG.")
GENERIC_ATTRIBUTES_PARSER.add_argument("--background", '-B', type=utils.Colour, nargs='?', default=NOTSET,
	help="Set background colour attribute, use #rrggbb, html colour names or leave blank.")
GENERIC_ATTRIBUTES_PARSER.add_argument("--fill", '-F', type=utils.Colour, nargs='?', default=NOTSET,
	help="Set polygon & circle fill colour attribute, use #rrggbb, html colour names or leave blank. Maps to 'fill' in SVG.")
GENERIC_ATTRIBUTES_PARSER.add_argument("--width", '-W', type=utils.arg_non_negative_float, nargs='?', default=NOTSET,
	help="Set line width attribute in mm. Maps to 'stroke-width' in SVG.")
GENERIC_ATTRIBUTES_PARSER.add_argument("--height", '-H', type=utils.arg_non_negative_float, nargs='?', default=NOTSET,
	help="Set text height attribute in mm for all text on the layer")
GENERIC_ATTRIBUTES_PARSER.add_argument("--align", '-A', type=utils.TextAlignment, nargs='?', default=NOTSET,
	help="Set text alignment attribute as one of {left,centre,right}-{top,middle,bottom}.")
GENERIC_ATTRIBUTES_PARSER.add_argument("--diameter", "-D", type=utils.arg_non_negative_float, nargs='?', default=NOTSET,
	help="diameter to draw node locations as circles (not scaled)")

OUTPUT_LAYER_PARSER = cmd2.Cmd2ArgumentParser(add_help=False)
OUTPUT_LAYER_PARSER.add_argument("output_layer", type=utils.layer_type, nargs='?',
	help=f"Destination layer for output, if not given then a new layer named after the command will be created.")

SINGLE_INPUT_LAYER_PARSER = cmd2.Cmd2ArgumentParser(add_help=False)
SINGLE_INPUT_LAYER_PARSER.add_argument("layer", type=utils.layer_type,
	help="Layer containing data to process.")

APPEND_OPTION_PARSER = cmd2.Cmd2ArgumentParser(add_help=False)
APPEND_OPTION_PARSER.add_argument("--append", "-a", action='store_true',
	help="appends data to existing data, default is to clear existing data")


'''
def add_layer_args(parser, inargs=1, ihelp=None, iname=None, ohelp=None, oname=None):
	"""Hlr to add arguments to an existing parser.
	Specifically for input layers and output layers, which are nearly always required, but differ slightly in nargs
	and help text."""
	assert inargs in '1*'.split()
	iplural = '' if inargs == '1' else 's'
	help = ihelp or f"Layer{iplural} with {iname} to process"
	parser.add_argument(f"input_layer{iplural}", type=utils.layer_type, nargs=inargs, help=help)
		help="Layer{} containing {iname} to process.")



input_layer_parser = cmd2.Cmd2ArgumentParser(add_help=False)

'''
