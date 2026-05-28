#!/usr/bin/env python3

import pytest

import utils

# Arg validators for argparse
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

def test_TextAlignment():
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

def test_wrap_validator_or_none():
	t = utils.wrap_validator_or_none(int)
	assert t("123") == 123
	assert t("0") == 0
	assert t("") == None

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

def test_ArgValidator():
	t = utils.ArgValidator(int)
	assert t('123') == 123
	with pytest.raises(ValueError) as exc:
		t('x')
	assert "Value 'x' failed to convert to type 'int'." in str(exc)

def test_ArgValidator_validator():
	def non_neg(a):
		if a < 0:
			raise ValueError
		return a
	t = utils.ArgValidator(int, non_neg)
	assert t('123') == 123
	with pytest.raises(ValueError) as exc:
		t('-1')
	assert "Value '-1': invalid" in str(exc)

def test_ArgValidator_validator_custom_msg():
	def non_neg(a):
		"value must be >= 0"
		if a < 0:
			raise ValueError
		return a
	t = utils.ArgValidator(int, non_neg)
	assert t('123') == 123
	with pytest.raises(ValueError) as exc:
		t('-1')
	assert "Value '-1': value must be >= 0" in str(exc)

def test_arg_percent_or_absolute():
	assert utils.arg_percent_or_absolute('123.4') == pytest.approx(123.4)
	assert utils.arg_percent_or_absolute('1.4%') == pytest.approx(-1.4)
	with pytest.raises(ValueError):
		utils.arg_percent_or_absolute('foo')
	with pytest.raises(ValueError):
		utils.arg_percent_or_absolute('-1')
	with pytest.raises(ValueError):
		utils.arg_percent_or_absolute('-2%')
