import math

import layer_set, utils

# This is in a module so that other modules with commands can use it.
APPNAME = "sf"

# Very important constants.
PHI = (math.sqrt(5.0)+1.0)/2.0
PHI_2 = PHI*PHI

# Attribute types
ATTRIBUTES = (
	layer_set.Attribute("background",	str, 		"white", 	"Background colour for plot, ignored in layers."),
	layer_set.Attribute("diameter", 	float, 	1.0, 			"Diameter of circles centred around Nodes."),
	layer_set.Attribute("fill", 			str, 		None, 		"Fill colour for Cells (polygons) only."),
	layer_set.Attribute("colour", 		str, 		"white",	"Line colour for all Widgets."),
	layer_set.Attribute("width", 			float, 	0.50,			"Line width in mm for all Widgets."),
	layer_set.Attribute("align", 			str, 		"centre-middle",
																											"Text alignment, [left centre right]-[top middle bottom]."),
	layer_set.Attribute("height", 		float, 	3.0, 			"Text height in mm"),
)
ATTRIBUTE_NAMES = tuple([a.name for a in ATTRIBUTES])

WIDGETS = (
	layer_set.NodesWidget(),
	layer_set.LinesWidget(),
	layer_set.CellsWidget(),
	# layer_set.TextWidget(),
)
WIDGET_NAMES = tuple([a.NAME for a in WIDGETS])
