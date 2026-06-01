#!/usr/bin/env python3

import sys, os
sys.path.append(os.path.abspath('../src'))

import pytest

import utils

# Arg validators for argparse
#

def test_ArgValidator():
	t = utils.ArgValidator(int)
	assert t('123') == 123
	with pytest.raises(ValueError) as exc:
		t('x')
	assert "value 'x' cannot convert to 'int'." in str(exc)

def test_ArgValidator_validator():
	t = utils.ArgValidator(int, lambda x: x >= 0)
	assert t('123') == 123
	with pytest.raises(ValueError) as exc:
		t('-1')
	assert "value '-1' invalid" in str(exc)

@pytest.mark.parametrize("validator, good, good_val, bad_val, invalid_val", [
	(utils.arg_positive_int, "123", 123, "0.5", "0"),
	(utils.arg_positive_float, "123.45", 123.45, "x", "0.0"),
	(utils.arg_non_negative_int, "123", 123, "0.5", "-1"),
	(utils.arg_non_negative_float, "123.45", 123.45, "x", "-1.0"),
])
def test_canned_validator(validator, good, good_val, bad_val, invalid_val):
	assert validator(good) == good_val
	with pytest.raises(ValueError) as exc:
		validator(bad_val)
	with pytest.raises(ValueError) as exc:
		validator(invalid_val)

def test_arg_percent_or_absolute():
	assert utils.arg_percent_or_absolute('123.4') == pytest.approx(123.4)
	assert utils.arg_percent_or_absolute('1.4%') == pytest.approx(-1.4)
	with pytest.raises(ValueError):
		utils.arg_percent_or_absolute('foo')
	with pytest.raises(ValueError):
		utils.arg_percent_or_absolute('-1')
	with pytest.raises(ValueError):
		utils.arg_percent_or_absolute('-2%')

# Universal colour class.
#
@pytest.mark.parametrize("col, html, sstr", [
	("red", "#ff0000", "red"),
	("#f00", "#ff0000", "#f00"),
	("#ff0000", "#ff0000", "#ff0000"),
	(None, "none", "none"),
	("", "none", "none"),
	("none", "none", "none"),
	("None", "none", "none"),
])
def test_Colour(col, html, sstr):
	t = utils.Colour(col)
	assert str(t) == sstr
	assert t.html() == html

@pytest.mark.parametrize("col", [
	"#f000",
	"foo",
])
def test_Colour_bad(col):
	with pytest.raises(ValueError):
		utils.Colour(col)

def test_Colour_Colour():
	tt = utils.Colour("red")
	t = utils.Colour(tt)
	assert str(t) == "red"

# Text alignment as '{left centre right}-{top middle bottom}'
#

def test_TextAlignmentConstants():
	assert utils.TextAlignment.DEFAULT == "centre-middle"

@pytest.mark.parametrize("align, exp", (
 	('', 							"centre-middle"),
 	(None, 						"centre-middle"),
 	(' centre ', 			"centre-middle"),
 	(' center ', 			"centre-middle"),
 	(' left- ', 			"left-middle"),
 	(' left-left ', 	"left-middle"),
 	('top right', 		"right-top"),
 	('LEFT_Bottom', 	"left-bottom"),
))
def test_TextAlignment(align, exp):
	t = utils.TextAlignment(align)
	assert str(t) == exp

@pytest.mark.parametrize("align", (
 	'foo',
 	'left foo',
))
def test_TextAlignmentBad(align):
	with pytest.raises(ValueError) as exc:
		utils.TextAlignment(align)

'''
def test_TextAlignment(x):
	assert utils.TextAlignment("") == "centre-middle"
	assert utils.TextAlignment("Centre MIDDLE") == "centre-middle"
	assert utils.TextAlignment(" TOP - leFt") == "left-top"
	assert utils.TextAlignment(" bottom - right") == "right-bottom"

def test_TextAlignment_bad():
	with pytest.raises(ValueError):
		utils.TextAlignment("Foo")

def test_get_text_align():
	assert utils.get_text_align_h('a b') == 'a'
	assert utils.get_text_align_h('a b') == 'a'
	assert utils.get_text_align_v('a b') == 'b'
	assert utils.get_text_align_h('a -b') == 'a'

def test_get_text_align_bad():
	with pytest.raises(AssertionError):
		utils.get_text_align_h(' a ')
	with pytest.raises(AssertionError):
		utils.get_text_align_v('  ')
'''
# Rectangular extents class
#

def test_Extents_empty():
	t = utils.Extents()
	assert not t
	assert t.get() == [[0.0,0.0],[0.0,0.0]]
	assert t.width() == 0.0
	assert t.height() == 0.0
	assert t.max_size() == 0.0

def test_Extents_one():
	t = utils.Extents()
	t.update((1, 2.0))
	assert not t				# Still empty!
	assert t.get() == [[1.0,2.0],[1.0,2.0]]
	assert t.width() == 0.0
	assert t.height() == 0.0
	assert t.max_size() == 0.0

def test_Extents_two():
	t = utils.Extents()
	t.update((1, 2.0))
	t.update((0, 4.0))
	assert t				# Not empty.
	assert t.get() == [[0.0,2.0],[1.0,4.0]]
	assert t.width() == 1.0
	assert t.height() == 2.0
	assert t.max_size() == 2.0

# Layer names
#

@pytest.mark.parametrize("name", ('X', 'x', 'x1', 'x'*29, 'x'*30, 'A', 'a-B'))
def test_layer_name_good(name):
	assert utils.is_valid_layer_name(name)
	assert utils.layer_type(name) == name
@pytest.mark.parametrize("name", ('', '_', '_1', '-', '1a', 'x'*31))
def test_layer_name_bad(name):
	assert not utils.is_valid_layer_name(name)
	with pytest.raises(ValueError):
		utils.layer_type(name)


# Add arbitrary attributes to a function.
#

@utils.add_func_attr("foo")
def f1_test_add_func_attr(x):
	return x+1
@utils.add_func_attr("bar", 123)
def f2_test_add_func_attr(x):
	return x+1
def test_add_func_attr():
	assert f1_test_add_func_attr(1) == 2
	assert getattr(f1_test_add_func_attr, "foo") == True
	assert f2_test_add_func_attr(1) == 2
	assert getattr(f2_test_add_func_attr, "bar") == 123
