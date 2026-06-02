#!/usr/bin/env python3

from typing import List, Callable, Union, Annotated, Any
import re, math, sys, weakref
from copy import deepcopy

import utils

from pydantic import BaseModel, ValidationError, BeforeValidator
import svgwrite
from svgwrite import mm

"""
LayerSet holds a number of Layers. It also can supply a value for an Attribute if not found in the Layer.
A Layer holds:
 One or zero Attributes, a single value such as a string, float, tuple for a colour, etc. They are described by a
	name/type, together with a default value.
 Several collections of Widgets, which are graphical elements, held as a list, the default for an unknown Widget is
	an empty list. Each Widget is either a point or a collection of points. Widgets can be accessed as a tuple, or with
	methods, e.g. w.x or w.coords[0] or w[0] are equivalent.
	Widgets can have extra data held as attributes, or read from the Layer
"""

class Attribute:
	"""Little class to hold an Attribute, which is an instance of a user supplied type."""
	def __init__(self, name:str, type, value, desc=""):
		self.name, self.type, self.desc = name, type, desc
		self._value = None if value is None else self.type(value)

	def clear(self):
		self._value = None
	def _set(self, v):
		self._value = self.type(v)
	value = property(fset=_set, fget=lambda self: self._value, doc="Set/get value, set converts to correct type.")

	def dump(self, sigfigs:int=4):
		try:
			val_s = f"{float(self._value):.{sigfigs}f}"
		except Exception:
			val_s = str(self._value)
		return f"{self.name} = {val_s}"
	def __repr__(self):
		return f"Attribute: {self.dump()}"
	def __str__(self):
		return str(self._value)

class NodesModel(BaseModel):
	def validate_inner_list(v: Any) -> Any:
		if not isinstance(v, (list, tuple)):
			raise ValueError("Inner element must be a list or tuple")
		if not (2 <= len(v) <= 3):
			raise ValueError("Inner list must contain 2 or 3 floats")
		if len(v) == 3 and v[2] <= 0:
			raise ValueError("Third element must be > 0")
		return [float(x) for x in v]

	items: Annotated[
		List[Annotated[List[float], BeforeValidator(validate_inner_list)]],
		"list of list of 2 or 3 floats, 3rd > 0"
	]

def validate_nodes(d):
	return NodesModel(items=d).items

class CellsModel(BaseModel):
	def validate_inner_list(v: Any) -> Any:
		if not isinstance(v, (list, tuple)):
			raise ValueError("Inner element must be a list or tuple")
		if len(v) != 2:
			raise ValueError("Inner list must contain 2 floats")
		return [float(x) for x in v]

	items: Annotated[
		List[List[Annotated[List[float], BeforeValidator(validate_inner_list)]]],
		"list of list of list of 2 floats."
	]

def validate_cells(d):
	return CellsModel(items=d).items

def validate_text(w):
	try:
		assert type(w) is list
		for x,y,t in w:
			assert type(x) is float and type(y) is float and type(t) is str
	except Exception:
		raise ValueError()
	return w

class WidgetBase:
	"""Base class for a graphical widget.
	Widgets hold a set of *items*, each item is a graphical entity like point, line, polygon, text, etc.
	Each item is an x,y tuple with possibly extra data appended."""

	NAME = None                   # Define in subclass

	def __init__(self):
		self.clear()
	def clear(self):
		self.items = []

	def _validate_data(self, data):
		"""Dual purpose function to validate data for the set() function and to validate the data member as an invariant.
		Overload in child classes."""
		raise RuntimeError

	def set(self, data, append=False):
		"""Either set or append data. Note that the data items for append are still enflosed in a list, eg:
		to set a list of nodes set([[1,2],[3,4]]), but to _append_ a third item you would call set([[5,6]], append=True)"""
		data = self._validate_data(data)
		if not append:
			self.items = data
		else:
			self.items += data
		self._validate_data(self.items)

	def get_items_canonical(self, container):
		"""Weird little method that allows subclasses to access the containing layer for the Widget to access attributes
		and other data for building a canonical representation of the items.
		The simple example is that Nodes can have a diameter defined as a layer attribute."""
		return self.items

	def get_item_coords(self, pos:str="mid"): # -> List[List[float, float]]:
		"""Useful function that gives the coordinates of a generic point of the widget *items*, that mat be a
		point, line, polygon, whatever.
		The point may either be at the smallest or largest magnitude (distance from origin) of the object or the "middle",
		whatever makes sense for the object."""
		return [self._do_get_item_coords(it, pos) for it in self.items]

	def _dump_summary(self):
		return f"len={len(self.items)}"

	def dump(self, sigfigs:int=2, width:int=80, summary=False):
		leader=f"Widget {self.NAME}: "
		if summary:
			return leader + self._dump_summary()
		else:
			return utils.dump(self.items, leader=leader, sigfigs=sigfigs, width=width)

	def __bool__(self):
		"Check if any data in this widget."
		return bool(self.items)

	def foreach_coord(self, func:Callable[List[float], None], env=None):
		"""Call function func for each point in all items in the widget, with environment variable env."""
		raise RuntimeError

	def _foreach_coord_in_list(self, vals, func:Callable[List[float], None], env=None):
		"Call user func with env over all coords."
		for pt in vals:
			func(pt, env)

	def update_extents(self, extents, container):
		"Update the extents object with data from the widget."
		for item in self.get_items_canonical(container):
			for pt in self._get_item_extents(item):
				extents.update(pt)

	def _get_item_extents(self, item):
		"Return list of points to define extents."
		raise RuntimeError

	def transform_item_coords(self, func: Callable[List[float], List[float] | None]) -> None:
		"""Iterate over each item in the widget, which might be a point or a list of points, possibly with added attributes.
		Then run the user function on each point in the item. If it returns false then the point is removed. If the
		transformed item is false then remove the item from the widget."""
		raise RuntimeError

	def _transform_list_points(self, func, pts):
		if not func:								# Default to identity function.
			func = lambda x: x
		return list(filter(None, [func(p) for p in pts]))

	def __repr__(self):
		return self.dump()

class NodesWidget(WidgetBase):
	NAME = "nodes"
	def __init__(self):
		super().__init__()

	def _validate_data(self, data):
		"List or tuple of 2 or 3 floats."
		return validate_nodes(data)

	def _do_get_item_coords(self, item, pos):
		return [item[0], item[1]]						# pos arg ignored: a node (point) is dimensionless.

	def get_items_canonical(self, container):
		"Special for nodes: return a list of 3 tuples with node either from item or diameter attribute."
		dia = container.get_attr("diameter") 															# Will default if layer attribute not found.
		assert dia
		return [nd + ([dia] if len(nd) == 2 else []) for nd in self.items]

	def _get_item_extents(self, item):
		x,y,d = item
		return (x-d/2,y-d/2), (x+d/2,y+d/2)

	def transform_item_coords(self, func: Callable[List[float], List[float] | None]) -> None:
		self.items = self._transform_list_points(func, self.items)

	def foreach_coord(self, func:Callable[List[float], None], env=None):
		self._foreach_coord_in_list(self.items, func, env)

class TextWidget(NodesWidget):
	NAME = "text"
	def __init__(self):
		super().__init__()

	def _validate_data(self, data):
		"List or tuple of 2 floats and a string."
		return validate_text(data)

	def _get_item_extents(self, item):
		return (0.0, 0.0), (0.0, 0.0)

	#TODO: Override get_items_canonical

class NodeSetWidgetBase(WidgetBase):
	def __init__(self):
		super().__init__()

	def _validate_data(self, data):
		"List of lists or tuple of 2 floats."
		return validate_cells(data)

	def _do_get_item_coords(self, item, pos):
		if pos in ('min', 'max'):
			dists = sorted([(math.hypot(xy[0], xy[1]), xy) for xy in item], key=lambda p: p[0])
			return dists[0][1] if pos == 'min' else dists[-1][1]
		return self._do_get_item_coords_mid(item)

	def _get_item_extents(self, item):
		return item

	def transform_item_coords(self, func: Callable[List[float], List[float] | None]) -> None:
		self.items = list(filter(None, [self._transform_list_points(func, pts) for pts in self.items]))

	def foreach_coord(self, func:Callable[List[float], None], env=None):
		for item in self.items:
			self._foreach_coord_in_list(item, func, env)

	def _dump_summary(self):
		return f"len={len(self.items)} [{','.join([str(len(it)) for it in self.items])}]"

class CellsWidget(NodeSetWidgetBase):
	NAME = "cells"
	def __init__(self):
		super().__init__()

	def _do_get_item_coords_mid(self, item):
		centroid = utils.cell_to_polygon(item).centroid
		return [centroid.x, centroid.y]

class LinesWidget(NodeSetWidgetBase):
	NAME = "lines"
	def __init__(self):
		super().__init__()

	def _do_get_item_coords_mid(self, item):
		N = len(item)
		assert N > 0								# Should only be called for non-empty list.
		if N == 1:									# Easy!
			return item[0]
		M = N//2
		if N % 2:                   # Easy with an odd number of points!
			return item[M]
		else:                       # Need to compute line midpoint
			e = item[M-1:M+1]
			return [(e[1][i]+e[0][i])/2 for i in range(2)]

class Layer:
	"""Container for Widgets, Attributes and a name.
	This class got absurdly compliocated when I tried to get smart with overloading attribute access. Took hours to get
	it working only to have it fall over when integrated with cmd2. Since the name of the item is usually in a string
	a method works well."""
	def __init__(self, name:str, attributes:List[Attribute], widgets:List[WidgetBase], parent=None):
		super().__setattr__('_attributes', {a.name: a for a in attributes}) # Set of allowed attributes to give default values.
		super().__setattr__('_widgets', {w.NAME: w for w in widgets})		# Set of Widgets.
		super().__setattr__('_parent',  weakref.ref(parent) if parent else None)# Link to parent to give default attribute values.
		super().__setattr__('name', name)

	def __setattr__(self, name, value):
		#print(name, value)
		if hasattr(self, name):
			super().__setattr__(name, value)
		else:
			raise AttributeError(f"Layer has no attribute '{name}'")

	def clone(self, name):
		"""Return a copy of self."""
		cloned_attributes = deepcopy(list(self._attributes.values()))
		for attr in cloned_attributes:
			attr.clear()        # Clear value in copy.
		cloned_widgets = deepcopy(list(self._widgets.values()))
		for w in cloned_widgets:
			w.clear()
		return Layer(name, cloned_attributes, cloned_widgets, parent=self)

	def get_attr(self, attr_name:str):
		attr = self._attributes[attr_name]
		if attr.value is not None:
			return attr.value
		parent = self._parent() if self._parent else None			# Deref link by calling it. Might return None if linkee deleted.
		return parent.get_attr(attr_name) if parent else None
	def set_attr(self, attr_name:str, value):
		self._attributes[attr_name].value = value

	def widget(self, widget_name:str):
		try:
			return self._widgets[widget_name]
		except KeyError:
			raise AttributeError(f"No widget {widget_name} in layer {self.name}.")

	def widgets(self):
		"Return names of widgets that are not empty."
		return tuple([w_name for w_name in self.WIDGET_NAMES if self.gey(w_name)])

	def dump_attributes(self, attr_from_parent:bool=False):
		return '; '.join(
			[f"{at.name}={self.get_attr(at.name) if attr_from_parent else at.value}" for at in self._attributes.values()])

	def dump(self, attr_from_parent:bool=False, sigfigs:int=2, width:int=80, summary:bool=False):
		dumps = [f"Layer {self.name}:"]
		dumps.append(self.dump_attributes(attr_from_parent) + ';')
		for w in self._widgets.values():
			dumps.append(w.dump(sigfigs=sigfigs,width=width, summary=summary))
		return ' '.join(dumps)

	def foreach_widget_item(self, funcdict:dict, env=None):
		"""Odd function that makes it easy to iterate over a set of widgets, running a function on each item in the widget.
		An arbitrary object may be supplied to the function, which should have the signature f(List[len > 2], env)"""
		assert set(funcdict.keys()) <= set(self.WIDGET_NAMES)

		for w_name, user_func in funcdict.items():					# User function to run on all things in the item.
			widget = self.widget(w_name)											# Get widget.
			if user_func:																			# Only call func if there is one!
				for it in widget.get_items_canonical(self):			# Iterate over all items in the widget.
					user_func(it, env)

	def _update_widget_names(self, widget_names:List[str]|None) -> List[str]:
		if widget_names is None:
			widget_names = self.WIDGET_NAMES
		else:
			assert set(widget_names) <= set(self.WIDGET_NAMES)
		return widget_names

	def update_extents_widgets(self, extents, widget_names:List[str]|None=None):
		widget_names = self._update_widget_names(widget_names)
		for w_name in widget_names:
			self.widget(w_name).update_extents(extents, self)							# Update extents for all items in widget with extra data from layer if required.

	"""We have a need to filter & transform the items. The use cases are:
	1. For all points in Nodes, Lines & Cells:
		- Transform, leaving them in order, e.g. for scaling.
		- Change the order, e.g for sorting or randomisation.
		- Filter them, eg to remove outliers

	2. For Lines & Cells only, the same operation but on the objects themselves.

	These are completely different operations, so are handled by different functions. """

	def transform_item_coords(self, transform: Callable[List[float], List[float] | None], widget_names:List[str]|None=None) -> None:
		"""Iterate over all layers and run a function over each point in the given data items, either transforming it or
		removing it if the function returns None."""
		widget_names = self._update_widget_names(widget_names)
		for w_name in widget_names:
			self.widget(w_name).transform_item_coords(transform)

	ATTRIBUTE_NAMES = property(fget=lambda self: tuple(self._attributes.keys()),
		doc="Tuple of all attribute names.")
	WIDGET_NAMES = property(fget=lambda self: tuple(self._widgets.keys()),
		doc="Tuple of all widget names.")

	def foreach_coord(self, func, env=None, widget_names=None):
		widget_names = self._update_widget_names(widget_names)
		for w_name in widget_names:
			self.widget(w_name).foreach_coord(func, env)

class LayerSet:
	"""A container for Layer objects. Knows how to plot, serialise & dump.
	A prototype Layer is provided which can also have default Attribute values."""

	# Purposely illegal layer name that allows access to prototype/parent layer.
	PROTO_LAYER_NAME = "_Default"

	# Supported plot formats.
	PLOT_FORMATS = "dxf svg".split()

	def __init__(self, layer_proto:Layer, sigfigs=2):
		layer_proto.name = self.PROTO_LAYER_NAME							# Name it for dump output.
		self.layers = {self.PROTO_LAYER_NAME: layer_proto}         # Single layer is cloned when we make a new layer.
		self.sigfigs = sigfigs

	ATTRIBUTE_NAMES = property(fget=lambda self: self.get(self.PROTO_LAYER_NAME).ATTRIBUTE_NAMES,
		doc="Tuple of all attribute names.")
	WIDGET_NAMES = property(fget=lambda self: self.get(self.PROTO_LAYER_NAME).WIDGET_NAMES,
		doc="Tuple of all widget names.")

	def get(self, layer_name:str) -> Layer:
		"""Return an existing layer, or create a new one if not."""
		if layer_name != self.PROTO_LAYER_NAME:
			assert utils.is_valid_layer_name(layer_name)
		if layer_name not in self.layers:
			self.layers[layer_name] = self.get(self.PROTO_LAYER_NAME).clone(layer_name)
		return self.layers[layer_name]

	def delete_layer(self, layer_name: str) -> None:
		assert layer_name in self.layers and layer_name != self.PROTO_LAYER_NAME
		del self.layers[layer_name]

	def dump(self, layer_names:List[str]|None=None, summary:bool=False, attr_from_parent: bool=False, sigfigs=4, width=80) -> str:
		"Return dump of data for specified layers, or all if not."
		if type(layer_names) is str:
			layer_names = layer_names.split()
		if not layer_names:
			layer_names = self.layer_names()
		# print(layer_names)
		dumps = [f"LayerSet:"]
		dumps.append(f"Default attributes: {self.get(self.PROTO_LAYER_NAME).dump_attributes(attr_from_parent=False)}")
		dumps += [self.get(ll).dump(attr_from_parent=attr_from_parent, summary=summary, sigfigs=self.sigfigs, width=width)
		 for ll in layer_names]
		return '\n'.join(dumps)

	def __repr__(self):
		return self.dump()

	def layer_names(self):
		"Get a tuple of all layer names in the set."
		return tuple([n for n in self.layers.keys() if n != self.PROTO_LAYER_NAME])

	def plot_svg(self, filename:str, layer_names:list[str]=None, use_dominant_baseline=False) -> None:
		if layer_names is None:
			layer_names = self.layer_names()
		assert set(layer_names) <= set(self.layer_names())

		dwg = svgwrite.Drawing()
		background_colour = self.get(self.PROTO_LAYER_NAME).get_attr("background")		# Retrieve from factory layer.
		dwg.add(dwg.rect(insert=(0,0), size=('100%', '100%'), fill=utils.Colour(background_colour).html()))
		extents = utils.Extents()

		H_ALIGN = {'left': 'start', 'centre': 'middle', 'right': 'end'}
		V_ALIGN = {'top': 'hanging', 'middle': 'middle', 'bottom': 'baseline'}
		V_ALIGN_OFFSET = {'top': 1.0, 'middle': 0.5, 'bottom': 0.0}

		ATTRIBUTE_MAP = [
			["fill",   "fill",              lambda c: utils.Colour(c).html()],
			["colour", "stroke",            lambda c: utils.Colour(c).html()],
			["width",  "stroke-width",      lambda x: x],		# Let X... equal... X...
			["height", "font_size",         lambda x: x],
			["align",  "text_anchor",       lambda x: H_ALIGN[x.align_h]],
		]
		if use_dominant_baseline:       # This attribute is only supported by browsers & Inkscape.
			ATTRIBUTE_MAP.append(["align",  "dominant_baseline",  lambda x: V_ALIGN[x.align_v]])

		for layer in [self.get(l) for l in layer_names]:
			# SVG has groups to set common attributes and collect objects. So we sort out attributes first.
			#TODO: Fix V alignment.
			if use_dominant_baseline:
				v_align_offset = 0.0
			else:
				v_align_offset = V_ALIGN_OFFSET[layer.get_attr("align").align_v] * layer.get_attr("height")
			#print(f"v_align={v_align_offset}")
			layer_attrs = {no: conv(layer.get_attr(ni)) for ni, no, conv in ATTRIBUTE_MAP}
			layer_attrs["font-family"] = "Roboto"
			g_layer = dwg.add(dwg.g(id=layer.name, **layer_attrs))

			# Functions that add widget _items_ to the dwg.
			def drawfunc_node(ci, env):
				env.add(dwg.circle(center=(ci[0], ci[1]), r=ci[2]/2))
			def drawfunc_line(ln, env):
				env.add(dwg.polyline(points=ln))
			def drawfunc_cell(ln, env):
				env.add(dwg.polygon(points=ln))
			def drawfunc_text(txt, env):
				env.add(dwg.text(txt[2], insert=(txt[0],txt[1]-v_align_offset)))
			DRAWFUNCS = {"nodes": drawfunc_node, "lines": drawfunc_line, "cells": drawfunc_cell, "text": drawfunc_text}

			layer.foreach_widget_item(DRAWFUNCS, g_layer)
			layer.update_extents_widgets(extents, list(DRAWFUNCS.keys()))

		lb = extents.get()[0]
		dwg['width'] = extents.width()*mm
		dwg['height'] = extents.height()*mm
		dwg.viewbox(lb[0], lb[1], extents.width(), extents.height())

		img = dwg.tostring()
		# First element will be something like: "<rect fill="rgb(50,50,50)" height="100%" width="100%" x="0" y="0" />"
		def set_background(m):
			bg = m.group()
			bg = bg.replace('x="0"', f'x="{lb[0]}"')
			bg = bg.replace('y="0"', f'y="{lb[1]}"')
			return bg
		img = re.sub(r"<rect.*?/>", set_background, img)
		open(filename, 'wt').write(img)

'''
	def get_text_with_attributes(self, layer:str): # -> List[List[float, float, str, float, str]]:
		"Given a list from the 'text' data key, add text height & alignment. So returns [x, y, text, height, alignment]"
		text_height, text_alignment = [self.get_data(layer, attr) for attr in "height align".split()]
		return [t + [text_height, text_alignment] for t in self.get_data(layer, "text")]
'''
