#!/usr/bin/env python3

import sys, re, pprint, math, functools, argparse, fnmatch
from typing import Callable, Any, Tuple, List

from PIL import ImageColor
from shapely.geometry import Polygon


def expand_items(items:tuple[str], spec:list[str]) -> tuple[list[str], list[str]]:
	"""Given a tuple of items, take a spec consisting of strings, each may either be an item in the items or a regex
	matching multiple items, and output a list of matches in the items tuple, and a list of specs that did not
	result in one or more matches.
	The found results are in the same order as the items."""
	found, not_found = set(), []
	for ss in spec:
		f_found = False
		for it in items:
			if fnmatch.fnmatchcase(it.lower(), ss.lower()):
				f_found = True
				found.add(it)
		if not f_found and 0 == sum([x in ss for x in "[]*?"]):
			not_found.append(ss)
	return [x for x in items if x in found], not_found

'''Validators for use with cmd2 should act like simple types, so that have a value set by being called, then
cmd2 will give an error message that makes sense.'''

class ArgValidator:
	"""Wrapper for a simple type that can wrap a simple type and validate the resulting conversion. """
	def __init__(self, t:type, validator:Callable[Any, Any]|None=None, name=None):
		self.t, self.validator = t, validator
		self.name = name or self.t.__name__
	def __repr__(self) -> str:
			"""Will be printed as the 'argument type' to user on syntax or range error."""
			return f"{self.name}"
	def __call__(self, arg: str) -> Any:
		try:
			arg = self.t(arg)
		except Exception:
			raise ValueError(f"value '{arg}' cannot convert to '{self.t.__name__}'.")
		if self.validator and not self.validator(arg):
			raise ValueError(f"value '{arg}' invalid")
		return arg

arg_positive_int = ArgValidator(int, lambda x: x>0, "PositiveInt")
arg_positive_float = ArgValidator(float, lambda x: x>0, "PositiveFloat")
arg_non_negative_int = ArgValidator(int, lambda x: x>=0, "NonNegativeInt")
arg_non_negative_float = ArgValidator(float, lambda x: x>=0, "NonNegativeFloat")

class Colour:
	"""A universal colour type, may be set with css colours or html colours like "#f00".
	For now we have opaque colours and the false value representing full transparency."""
	#TODO: get rid of PIL dependancy.
	def __init__(self, col:str|None):
		"Colour value as string"
		if type(col) is type(self):
			self.col = col.col
		else:
			self.col = None
			if col and col.lower() != "none":
				try:
					rgb = ImageColor.getrgb(col)
					if len(rgb) != 3:
						raise ValueError
					self.col = col
				except ValueError:
					raise ValueError(f"Colour: cannot parse {repr(col)}.")

	def html(self):
		if not self.col:
			return "none"
		else:
			c = ImageColor.getrgb(self.col)
			return f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"

	def __str__(self):
		return self.col or "none"

class Extents:
	"""Keeps track of extents (bounding) box of a set of points."""
	def __init__(self):
		self.extents = None

	def check_invariant(self):
			assert self.extents[0][0] <= self.extents[1][0] and self.extents[0][1] <= self.extents[1][1]
	def update(self, pt: Tuple[float,float]) -> None:
		pt = [float(p) for p in pt[:2]]
		if not self.extents:
			self.extents = [list(pt), list(pt)]
		else:
			self.check_invariant()
			if pt[0] < self.extents[0][0]: self.extents[0][0] = pt[0]
			if pt[1] < self.extents[0][1]: self.extents[0][1] = pt[1]
			if pt[0] > self.extents[1][0]: self.extents[1][0] = pt[0]
			if pt[1] > self.extents[1][1]: self.extents[1][1] = pt[1]
			self.check_invariant()
	def get(self):
		return self.extents or [[0,0],[0,0]]
	def width(self):
		return self.get()[1][0] - self.get()[0][0]
	def height(self):
		return self.get()[1][1] - self.get()[0][1]
	def max_size(self):
		return max(self.height(), self.width())
	def __bool__(self):
		return self.max_size() > 0.0
	def __repr__(self):
		return f"Extents: ({','.join(map(str, self.extents[0]))}), ({','.join(map(str, self.extents[1]))})"

def arg_percent_or_absolute(a):
	"must be a positive number or percentage"
	percent = -1 if a.endswith("%") else 0
	val = float(a[:-1]) if percent else float(a)
	if  val < 0.0:
			raise ValueError
	return -val if percent else val

def is_valid_layer_name(a:str) -> bool:
	"Check if a string is a valid layer ID. Leading letter then any alphanumeric or '-' or '_'. Max length 30 chars"
	RE_ID = r"(?i)[a-z][a-z0-9_-]{0,29}"
	return re.fullmatch(RE_ID, a)

def layer_type(a:str) -> str:
	"Used to validate a legal layer name."
	if not is_valid_layer_name(a):
		raise ValueError(f"bad layer name {a}")
	return a

''' Remember a decorator used as @foo is equivalent to f = foo(f).
So if the decorator had arguments,

	@decorator_with_args(arg)
	def foo(*args, **kwargs):
    pass

translates to

	foo = decorator_with_args(arg)(foo)

So decorator_with_args is a function which accepts a custom argument and which returns the actual decorator (that will be applied to the decorated function).
'''

def add_func_attr(name, value=True):
	"Add an attribute to a function, with default value True."
	def decorator(func):
			setattr(func, name, value)
			return func
	return decorator

class TextAlignment:
	"""Captures horizontal & vertical  text alignment as one of left, centre, right & one of top, middle, bottom
	with default being left, middle.
	Alignment styled as "left-middle" with a hyphen, but any punctuation or space will do as a separator on input.
	Case in ignored and "center" is begrudgingly allowed as a synonym for "centre".
	Any number of terms can be supplied with each overriding either the default or the last term for H or V."""

	ALIGNMENT_TERMS_H, ALIGNMENT_TERMS_V = 'left centre right'.split(), 'top middle bottom'.split()
	DEFAULT = "centre-middle"
	def __init__(self, align:str):
		self._set(align or self.DEFAULT)
	def _set(self, align:str):
		h, v = self.DEFAULT.split('-')
		for a_term in re.split(r"[^a-z]+", align.lower()):
			if a_term:
				if a_term == 'center':
					a_term = 'centre'
				if a_term in self.ALIGNMENT_TERMS_H:
					h = a_term
				elif a_term in self.ALIGNMENT_TERMS_V:
					v = a_term
				else:
					raise ValueError(f"Alignment '{align}' invalid.")
		self.h, self.v = h, v
	def __str__(self):
		return f"{self.h}-{self.v}"
	align_h = property(fget=lambda self: self.h, doc="Return horizontal alignment")
	align_v = property(fget=lambda self: self.v, doc="Return vertical alignment")

#
#

# Type for the nodes, either [x,y] or [x,y,r]
Node = list[float,float]|list[float,float,float]
Nodes = list[Node]

# Type for cells, lists of list of 2 floats.
Cell = list[list[float,float]]
Cells = list[Cell]

def cell_to_polygon(c:Cell) -> Polygon:
	"Helper to turn a cell into a shapely Polygon."
	return Polygon(c)
def polygon_to_cell(p:Polygon) -> Cell:
	"Helper to turn a shapely Polygon into a cell."
	return [list(xy) for xy in p.exterior.coords[1:]]

def sort_nodes(nodes:Nodes):
	"Sort a list of nodes as [x,y] or [x,y,d] by distance from origin"
	nodes.sort(key=lambda a: math.hypot(a[0], a[1]))

def largest_radius(nodes:Nodes):
	magnitudes = [math.hypot(a[0], a[1]) for a in nodes]
	return max(magnitudes, default=0.0)

def to_cartesian(nodes_p:Nodes):
	"""Convert the list of polar nodes to cartesian, keeping any extra values."""
	return [[r*math.cos(θ), r*math.sin(θ)] + ex for r,θ,*ex in nodes_p]


class FormatPrinter(pprint.PrettyPrinter):
	"""Stolen from Gemini. E.g:
		printer = FormatPrinter({float: "%.2f"})
		printer.pprint(data)
		"""

	def __init__(self, formats, **kwargs):
		super(FormatPrinter, self).__init__(**kwargs)
		self.formats = formats

	def format(self, obj, ctx, maxlvl, lvl):
		try:
			return self.formats[type(obj)] % obj, True, False
		except KeyError:
			return pprint.PrettyPrinter.format(self, obj, ctx, maxlvl, lvl)

def dump(stuff, leader="", sigfigs=2, width=80):
	printer = FormatPrinter({float: f"%.{sigfigs}f"}, compact=True, sort_dicts=False, indent=2, width=width)
	return f"{leader}{printer.pformat(stuff)}"

# Not tested.
#

def dump_custom_options(ns:argparse.Namespace, leader=None) -> str:
	"Format all options that are not special cmd2 options that are prefixed 'cmd2...'."
	if not leader:
		leader = 'Args'
	return f'{leader}: {", ".join([f"{k}={v}" for k,v in vars(ns).items() if not k.startswith('cmd2')])}'

