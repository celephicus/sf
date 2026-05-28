import re, pprint, math, functools, argparse
from typing import Callable, Any, Tuple, List

from PIL import ImageColor
from shapely.geometry import Polygon

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

class Colour:
	"""A universal colour type, may be set with css colours or html colours like "#f00".
	For now we have opaque colours and the false value representing full transparency."""
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

def exclude_from_undo():
	"Cmd2 command decorator to set a command to not be recorded in the undo list."
	def decorator(f):
		setattr(f, "no_undo", True)
		return f
	return decorator

ALIGNMENT_TERMS_H, ALIGNMENT_TERMS_V = 'centre left right'.split(), 'middle top bottom'.split() # Default is first item.
ALIGNMENT_TERMS = ALIGNMENT_TERMS_H + ALIGNMENT_TERMS_V
def get_raw_text_alignment_items(a):
	return [] if a is None else [aa for aa in re.split(r"[^a-z]+", a.lower()) if aa]
def TextAlignment(a):
	"""Align may be:  (left, centre, right) combined with (top, middle, bottom) with centre & middle as defaults.
	Any non-alpha character separates the values."""
	tt = get_raw_text_alignment_items(a)
	if [it for it in tt if it not in ALIGNMENT_TERMS]:
		raise ValueError(f"Unknown alignment spec {a}.")
	h, v = ALIGNMENT_TERMS_H[0], ALIGNMENT_TERMS_V[0]
	for it in tt:
		if it in ALIGNMENT_TERMS_H:
			h = it
		elif it in ALIGNMENT_TERMS_V:
			v = it
	return '-'.join((h,v))	# Canonical version that can be parsed again.
def get_text_align_h(a):
	"Return canonical H text alignment "
	items = get_raw_text_alignment_items(a)
	assert len(items) == 2
	return items[0]
def get_text_align_v(a):
	"Return canonical V text alignment "
	items = get_raw_text_alignment_items(a)
	assert len(items) == 2
	return items[1]

def wrap_validator_or_none(validator):
	"Adds the facility to accept an empty string as None to a validator."
	return lambda a: None if not a else validator(a)

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

arg_positive_int = ArgValidator(int, lambda x: x>0, "PositiveInt")
arg_positive_float = ArgValidator(float, lambda x: x>0, "PositiveFloat")
arg_non_negative_int = ArgValidator(int, lambda x: x>=0, "NonNegativeInt")
arg_non_negative_float = ArgValidator(float, lambda x: x>=0, "NonNegativeFloat")

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
