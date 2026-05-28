# Introduction
Coding the big ball of mud that has accreted features *viz.* `Sunflower`, I have realised that it is now very difficult to modify. I really need *language* that can generate patterns based on collections of graphics primitives, and then render them. The commands of this language can be combined in a pipeline to generate my two key use cases, Voronoi patterns based on a sunflower, and polygons based on the parastichy numbers in phyllotactic growth. Any custom processing is easy to add in at any stage.

The plan is to use the language to generate Sunflower a large 1200mm diameter steel flower.
Centre is a sunflower seed pattern that can be retrofitted with LEDs.
Surrounding this are a series of petals made of logarithmic spirals with two parastichy spirals forming quadrilaterals. The two shortest sides are both set *behind* the longest sides of the two petals adjacent. This will allow retrofitting of lighting strips.
Petals made of scrap roofing iron then plasma cut out. Could paint before cutting.
Design projected onto a bench by a fixed projector. Then design marked directly on stock and cut by hand.

## Plan
Start with a set of Python scripts reading/writing TOML, there is no  simpler markup language. This will develop usage and concepts.
Then move to the Python package [cmd2](https://cmd2.readthedocs.io/en/stable/) to make a little language.
Drive from a webpage.
### Rendering & Layers
First off we have a set of **Layers**, like DXF layers or SVG groups which define a set of default attributes for the primitives they contain. These attributes are based on SVG and include `stroke`, `color`, `fill`, etc.
Layer names are restricted to legal layer names for DXF, which are the regex `[a-z][a-z0-9-_]*`, case insensitive.
The primitives inherit these attribute and can override them, though this is rare.
One additional attribute hides layers/items analogous to the SVG `display` attribute.
The layer also has a multiline string not used for rendering. Holds comments pertaining to that layer.
### Primitives
Our primitives are:
**Points** are point coordinates possibly each with a diameter, though this can be set as a layer attribute.
**Polylines** are a set of arrays of points, defining a collection of lines, which may form closed polygons.
**Text** is list of `(x, y, <text>, height, [,<justification>])`, justification being `[LCR][TMB]`, default `LB`.


A layer typically has a maximum of one collection of graphics primitives in it. This makes it easy for the language to select data, there is simply only *one* set of primitives in the layer, being either **Points**, **Polylines** or **Text**.

## Reference Layer
However if if a layer is used as a canvas to hold items that will never be used in the final design, but need to be present in the rendered image for reference, e.g few circles or rectangles for scale indication and a text representation of the code used to generate it. It is never cut, in particular the text may be so small as to be unreadable but it is there in the image for reference.

As an idea, to generate sunflowers as a shell script. All take at least one layer as a positional  argument, maybe two. In this example new layers are created by being used.
```
sf sunflower seeds --nodes=130 --size=300 |       # Original nodes with extra for border.
sf voronoi seeds cells |                          # Generate Voronoi over all nodes, discards unbounded.
sf sort cells --count=100 |                       # Sort radially by distance and crop larger
sf centroid cells nodes |                         # Generate new nodes from centroid of cells.
sf border cells border --offset=2 |               # Make a border.
sf render "seeds, red, diameter=8.0"
          "nodes, green, diameter=8.0"
          "cells, blue, stroke=1.5"
          "border, yellow"
```

An example in TOML:
```
[seeds]
note = 'Starting points for design.'
diameter = 5.0
colour = 'red'
points = [[0.1, 2,3], ... ]
polys = [
	[[0.1, 2,3], ... ]
]
```



==Need to think how to make this pattern.==
Piece by Barklie Hebert.
![[image-29.png]]

From [Andy Giger's Paratichy Explorer](https://andygiger.com/science/parastichies/) I think two log spirals with divergence angles of 15°±0.2° will give two opposing spirals with parastichy numbers of 24
