#!/usr/bin/env python3

import os, sys
sys.path.append(os.path.abspath('../src'))

import pytest

from layer_set import *

#TODO: Use classes for tests.
# Attributes
def test_attribute():
	t = Attribute("foo", float, 0, "qwer")
	assert t.value == 0.0	# Convert to float.
	assert type(t.value) is float
	t.value = 1.23
	assert t.value == 1.23
	assert t.desc == "qwer"
	with pytest.raises(ValueError):
		t.value = 'fff'
	assert repr(t) == "Attribute: foo = 1.2300"

def test_attribute_init_bad():
	with pytest.raises(ValueError):
		Attribute("foo", float, "fff", "qwe")

def test_attribute_dump_f():
	t = Attribute("foo", float, 0.0)
	t.value = 1.23
	assert t.dump() == "foo = 1.2300"
	assert t.dump(sigfigs=1) == "foo = 1.2"
def test_attribute_dump_s():
	t = Attribute("foo", str, "bar")
	t.value = "123"    # Converted to float.
	assert t.dump() == "foo = 123.0000"

def test_attribute_clear():
	t = Attribute("foo", float, 1.23)
	t.value = 123
	assert t.value == 123.0
	t.clear()
	assert t.value == None

# Validators for nodes & cells.

def test_v_node():
	assert validate_nodes([]) == []
	assert validate_nodes([[1.0,2.0]]) == [[1.0,2.0]]
	assert validate_nodes([(1.0,2.0)]) == [[1.0,2.0]]	# Convert inner tuple to list.
	assert validate_nodes([[1,2]]) == [[1.0,2.0]]		# Convert int 2 float
	assert validate_nodes([[1.0,2.0], [1,2], [1,2,3]]) == [[1.0,2.0],[1.0,2.0], [1.0, 2.0, 3.0]]

@pytest.mark.parametrize("x", [
	'a',
	1,
	[[1,2,3,4]],
	[[1,2,-1]],
])
def test_v_node_bad(x):
	with pytest.raises(ValueError):
		validate_nodes(x)

def test_v_cells():
	assert validate_cells([]) == []
	assert validate_cells([[]]) == [[]]				# We do allow degenerate cells.
	assert validate_cells([[[1,2]]]) == [[[1.0,2.0]]]

@pytest.mark.parametrize("x", [
	'a',
	[[[1,]]],
	[[[1,2,3]]],
])
def test_v_cells_bad(x):
	with pytest.raises(ValueError):
		validate_cells(x)

def test_v_text():
	assert validate_text([]) == []
	assert validate_text([[1.0, 2.0, "foo"]]) == [[1.0, 2.0, "foo"]]

@pytest.mark.parametrize("w", [
	'a',
	[[1.0,2.0]],
	[[1.0,2.0,3.0]],
])
def test_v_text_bad(w):
	with pytest.raises(ValueError):
		validate_text(w)

# Widget: Nodes
def test_nodes_widget():
	t = NodesWidget()
	assert t.NAME == "nodes"
	assert t.items == []
	assert not t					# Empty
	t.set([[1.0,2.0]])
	assert t							# Not empty.
	assert t.items == [[1.0,2.0]]
	t.set([[11.0,12.0]])
	assert t.items == [[11.0,12.0]]
	t.set([[1.0,2.0]], append=True)
	assert t.items == [[11.0,12.0],[1.0,2.0]]
	t.set([[11.0,12.0, 3.0]])
	assert t.items == [[11.0,12.0, 3.0]]

	with pytest.raises(ValueError):
		t.set([[1.0]])										# Error: only 1 element.
	with pytest.raises(ValueError):
		t.set([[1.0, 2.0, -1.0]])					# Error: negative diameter.

	t.set([[11.0,12.0],[1.0,2.0]])
	assert t.dump() == "Widget nodes: [[11.00, 12.00], [1.00, 2.00]]"
	assert t.dump(summary=True) == "Widget nodes: len=2"

def test_nodes_widget_item_coords():
	t = NodesWidget()
	t.set([[11.0,12.0],[1.0,2.0, 33.0]])
	assert t.get_item_coords() == [[11.0,12.0],[1.0,2.0]]
	assert t.get_item_coords('min') == [[11.0,12.0],[1.0,2.0]]
	assert t.get_item_coords('mid') == [[11.0,12.0],[1.0,2.0]]
	assert t.get_item_coords('max') == [[11.0,12.0],[1.0,2.0]]
	assert t.get_item_coords() == t.get_item_coords("foo")

@pytest.fixture
def node_layer():
	l = Layer(														 # We needs a real-ish layer
		"realish",
		[Attribute("diameter", float, 1.0)],
		[NodesWidget()]
	)
	return l

def test_get_items_canonical_nodes(node_layer):
	t = node_layer.widget("nodes")
	t.set([[11.0,12.0],[1.0,2.0, 33.0]])
	assert(t.get_items_canonical(node_layer) == [[11.0,12.0,1.0],[1.0,2.0, 33.0]])

def test_nodes_widget_extents(node_layer):
	t = node_layer.widget("nodes")
	e = utils.Extents()

	t.set([[1.0,2.0]])
	t.update_extents(e, node_layer)
	assert e.get() == [[0.5,1.5],[1.5,2.5]]

	t.set([[2.0,3.0]])
	t.update_extents(e, node_layer)
	assert e.get() == [[0.5,1.5],[2.5,3.5]]

@pytest.mark.parametrize("func, exp", [
	(None,				[[1.0,2.0],[3.0,4.0],[5.0,6.0],[7.0,8.0,9.0]]),
	(lambda x: x,	[[1.0,2.0],[3.0,4.0],[5.0,6.0],[7.0,8.0,9.0]]),
	(lambda x: [x[0]*2]+x[1:] if x[0]<4 else None, [[2.0,2.0],[6.0,4.0]]),
	(lambda x: [x[0]*2]+x[1:] if x[0]>4 else None, [[10.0,6.0],[14.0,8.0,9.0]]),
])
def test_transform_item_coords_nodes(func, exp):
	t = NodesWidget()
	t.set([[1,2],[3,4],[5,6],[7,8,9]])
	t.transform_item_coords(func)
	assert t.items == exp

@pytest.mark.parametrize("widget, init_vals, exp", [
	(NodesWidget(), [[1,2],[3,4],[5,6]], [[1,2],[3,4],[5,6]]),
	(CellsWidget(), [[[1,2],[3,4]],[[5,6]]], [[1,2],[3,4],[5,6]]),
	(LinesWidget(), [[[1,2],[3,4]],[[5,6]]], [[1,2],[3,4],[5,6]]),
])
def test_foreach_coord(widget, init_vals, exp):
	pts = []
	widget.set(init_vals)
	widget.foreach_coord(lambda pt, env: env.append(pt), env=pts)
	assert pts == exp

#Widget: Cells & Lines common tests.
#
@pytest.mark.parametrize('t, name', [
	(CellsWidget(), "cells"),
	(LinesWidget(), "lines"),
])
def test_lines_cells_widget(t, name):
	assert t.NAME == name
	assert t.items == []
	assert not t					# Empty
	t.set([[(1,1)]])
	assert t							# Not empty.
	assert t.items == [[[1.0,1.0]]]
	t.set([[[1.0,1.0],[2.0,1.0],[2.0,2.0],[1.0,2.0]]])
	assert t.items == [[[1.0,1.0],[2.0,1.0],[2.0,2.0],[1.0,2.0]]]
	t.set([[(8,9)]], append=True)
	assert t.items == [[[1.0,1.0],[2.0,1.0],[2.0,2.0],[1.0,2.0]], [[8.0,9.0]]]

	with pytest.raises(ValueError):
		t.set([[[1.0]]])										# Error: only 1 element.
	with pytest.raises(ValueError):
		t.set([[[1.0, 2.0, -1.0]]])					# Error: 3 elements.

	t.set([[[11.0,12.0],[1.0,2.0]]])
	assert t.dump() == f"Widget {name}: [[[11.00, 12.00], [1.00, 2.00]]]"
	assert t.dump(summary=True) == f"Widget {name}: len=1 [2]"

@pytest.fixture
def lines_cells_layer():
	l = Layer(														 # We needs a real-ish layer
		"realish",
		[],
		[CellsWidget(), LinesWidget()]
	)
	return l

@pytest.mark.parametrize("w_name", ("cells", "lines"))
def verify_get_items_canonical(lines_cells_layer, w_name):
	t = lines_cells_layer.widget(w_name)
	t.set([[[1.0,1.0],[2.0,1.0],[2.0,2.0],[1.0,2.0]]])
	assert t.get_items_canonical(lines_cells_layer) == [[[1.0,1.0],[2.0,1.0],[2.0,2.0],[1.0,2.0]]]		# No effect.

# Paramettrizing with a static fixture.
@pytest.mark.parametrize("w_name", ("cells", "lines"))
def test_widget_extents(lines_cells_layer, w_name):
	t = lines_cells_layer.widget(w_name)
	e = utils.Extents()

	t.set([[[1.0,2.0],[3.0,4.0]]])
	t.update_extents(e, lines_cells_layer)
	assert e.get() == [[1.0,2.0],[3.0,4.0]]

	t.set([[[11.0,12.0],[13.0,14.0]]], append=True)
	t.update_extents(e, lines_cells_layer)
	assert e.get() == [[1.0,2.0],[13.0,14.0]]

# Cartesian product
@pytest.mark.parametrize("t", [CellsWidget(), LinesWidget()])
@pytest.mark.parametrize("func, exp", [
	(None,				[[[1.0,2.0],[3.0,4.0],[5.0,6.0],[7.0,8.0]],[[1.0,2.0],[3.0,4.0],[5.0,6.0],[7.0,8.0]]]),
	(lambda x: x,	[[[1.0,2.0],[3.0,4.0],[5.0,6.0],[7.0,8.0]],[[1.0,2.0],[3.0,4.0],[5.0,6.0],[7.0,8.0]]]),
	(lambda x: [x[0]*2]+x[1:] if x[0]<4 else None, [[[2.0,2.0],[6.0,4.0]],[[2.0,2.0],[6.0,4.0]]]),
	(lambda x: [x[0]*2]+x[1:] if x[0]>4 else None, [[[10.0,6.0],[14.0,8.0]],[[10.0,6.0],[14.0,8.0]]]),
])
def test_transform_item_coords_lines_cells(t, func, exp):
	t.set([[[1,2],[3,4],[5,6],[7,8]],[[1,2],[3,4],[5,6],[7,8]]])
	t.transform_item_coords(func)
	assert t.items == exp

# Lines Widget
#

def test_lines_widget_item_coords():
	t = LinesWidget()
	t.set([
		[[1,2],[2,4]],
	])
	assert t.get_item_coords() == [[1.5,3.0]]
	assert t.get_item_coords('mid') == [[1.5,3.0]]
	assert t.get_item_coords('min') == [[1.0,2.0]]
	assert t.get_item_coords('max') == [[2.0,4.0]]
	assert t.get_item_coords() == t.get_item_coords("foo")

# Cells Widget
#
def test_cells_widget_item_coords():
	t = CellsWidget()
	t.set([
		[[1.0,1.0],[2.0,1.0],[2.0,2.0],[1.0,2.0]],
		[[2,2],[3,2],[3,3],[2,3]],
	])
	assert t.get_item_coords() == [[1.5, 1.5], [2.5, 2.5]]
	assert t.get_item_coords('mid') == [[1.5, 1.5], [2.5, 2.5]]
	assert t.get_item_coords('min') == [[1.0, 1.0], [2.0, 2.0]]
	assert t.get_item_coords('max') == [[2.0, 2.0], [3.0, 3.0]]
	assert t.get_item_coords() == t.get_item_coords("foo")

# Layer
@pytest.fixture
def t_layer():
	l = Layer(
		"test",
		[Attribute("attr1", int, 1), Attribute("attr2", str, "foo")],
		[NodesWidget()]
	)
	l.widget("nodes").set([[1,2],[3,4]])
	return l

def test_layer_init(t_layer):
	assert t_layer.name == "test"
	assert t_layer.get_attr("attr1") == 1
	assert t_layer.get_attr("attr2") == "foo"
	t_layer.set_attr("attr1", 123)
	assert t_layer.get_attr("attr1") == 123

	assert t_layer.ATTRIBUTE_NAMES == ("attr1", "attr2")
	assert t_layer.WIDGET_NAMES == ("nodes",)

	assert t_layer.widget("nodes").items == [[1.0,2.0], [3.0,4.0]]
	assert t_layer.dump() == "Layer test: attr1=123; attr2=foo; Widget nodes: [[1.00, 2.00], [3.00, 4.00]]"

def test_layer_clone(t_layer):
	clone = t_layer.clone("cloned")
	assert clone._attributes["attr1"].value == None   # Clone has all attrs set to nil
	assert clone._attributes["attr2"].value == None   # Clone has all attrs set to nil
	assert clone.widget("nodes").items == []
	assert clone.get_attr("attr1") == 1            # But gets value from parent.
	assert clone.get_attr("attr2") == "foo"
	assert t_layer.get_attr("attr1") == 1

	t_layer.set_attr("attr1", 456)
	assert clone.get_attr("attr1") == 456            # Still gets value from parent.
	clone.set_attr("attr1", 789)
	assert clone.get_attr("attr1") == 789            # Value as set.

	clone.widget("nodes").set([[5,6]])
	assert clone.widget("nodes").items == [[5.0,6.0]]
	assert t_layer.widget("nodes").items == [[1.0,2.0], [3.0,4.0]]		# No overwrite of parent.

def test_layer_clone_delete_parent():
	parent = Layer("test", [Attribute("attr1", int, 1)], [])
	clone = parent.clone("cloned")
	assert clone.get_attr("attr1") == 1            # But gets value from parent.
	del parent
	assert clone.get_attr("attr1") == None            # No value set and no parent.

	clone.set_attr("attr1", 456)
	assert clone.get_attr("attr1") == 456            # Still gets value from parent.

def test_layer_bad_attr(t_layer):
	with pytest.raises(AttributeError):
		t_layer.foo = "foo"

def test_layer_dump(t_layer):
	assert t_layer.dump() == "Layer test: attr1=1; attr2=foo; Widget nodes: [[1.00, 2.00], [3.00, 4.00]]"
	clone = t_layer.clone("cloned")
	assert clone.dump(attr_from_parent=True) == "Layer cloned: attr1=1; attr2=foo; Widget nodes: []"
	assert clone.dump(attr_from_parent=False) == "Layer cloned: attr1=None; attr2=None; Widget nodes: []"

def proc_item_n(it, items): items.append(['N']+it)
def proc_item_c(it, items): items.append(['C']+it)
@pytest.mark.parametrize("funcdict, exp_items, exp_extents", [
	({}, 											[],																																				[[0.0,0.0],[0.0,0.0]]),
	({'nodes': proc_item_n}, 	[['N',1.0,2.0,1.0],['N',3.0,4.0,9.0]],																		[[-1.5,-0.5],[7.5,8.5]]),
	({'cells': proc_item_c}, 	[['C', [20.0, 21.0], [22.0, 23.0]], ['C', [30.0, 31.0], [32.0, 33.0]]],		[[20.0,21.0],[32.0,33.0]]),
])
def test_layer_foreach_widget_item(funcdict, exp_items, exp_extents):
	t = Layer(
		"test",
		[Attribute("diameter", float, 1.0)],
		[NodesWidget(), CellsWidget()]
	)
	t.widget("nodes").set([[1,2],[3,4,9]])
	t.widget("cells").set([[[20,21],[22,23]],[[30,31],[32,33]]])

	items = []
	t.foreach_widget_item(funcdict, items)
	assert items == exp_items

	extents = utils.Extents()
	t.update_extents_widgets(extents, list(funcdict.keys()))
	assert extents.get() == exp_extents

# LayerSet: the big one...

def test_layerset_init(t_layer):
	t = LayerSet(t_layer)
	assert t.layer_names() == ()
	assert t.ATTRIBUTE_NAMES == ("attr1", "attr2")
	assert t.WIDGET_NAMES == ("nodes",)

def test_layerset_new(t_layer):
	t = LayerSet(t_layer)
	l = t.get('foo')
	assert l.name == 'foo'
	assert t.layer_names() == ('foo',)
	assert t.get('foo') is l
	assert l.get_attr("attr1") == 1						# From parent.
	l.set_attr("attr1", 123)
	assert l.get_attr("attr1") == 123
	with pytest.raises(AssertionError):
		t.get("_foo")

def test_layerset_delete(t_layer):
	t = LayerSet(t_layer)
	t.get('foo')
	assert t.layer_names() == ('foo',)
	t.delete_layer('foo')
	assert t.layer_names() == ()
	with pytest.raises(AssertionError):
		t.delete_layer('foo')

def test_layerset_dump(t_layer):
	t = LayerSet(t_layer)
	l = t.get('foo')
	l.set_attr("attr1", 456)
	l.widget("nodes").set([[1.0,2.0], [3.0,4.0]])
	t.get("bar")

	assert t.dump(attr_from_parent=True) == """\
LayerSet:
Default attributes: attr1=1; attr2=foo
Layer foo: attr1=456; attr2=foo; Widget nodes: [[1.00, 2.00], [3.00, 4.00]]
Layer bar: attr1=1; attr2=foo; Widget nodes: []"""
	assert t.dump("bar", attr_from_parent=True) == """\
LayerSet:
Default attributes: attr1=1; attr2=foo
Layer bar: attr1=1; attr2=foo; Widget nodes: []"""

	assert t.dump(attr_from_parent=False) == """\
LayerSet:
Default attributes: attr1=1; attr2=foo
Layer foo: attr1=456; attr2=None; Widget nodes: [[1.00, 2.00], [3.00, 4.00]]
Layer bar: attr1=None; attr2=None; Widget nodes: []"""
	assert t.dump("bar", attr_from_parent=False) == """\
LayerSet:
Default attributes: attr1=1; attr2=foo
Layer bar: attr1=None; attr2=None; Widget nodes: []"""

