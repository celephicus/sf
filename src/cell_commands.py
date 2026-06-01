from typing import Tuple, List
import argparse, math
from pathlib import Path

import cmd2
import networkx as nx			# Abstract network operations

import utils, base_parser, sf2_common

from scipy.spatial import Voronoi
from shapely.geometry import Polygon
import shapelysmooth
import geopandas as gpd
from shapely.ops import unary_union

@cmd2.with_default_category('Line & Cell Commands')
class LineCellCommands(cmd2.CommandSet):
	def __init__(self):
		super().__init__()

	# Parastichy command -
	parastichy_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser.GENERIC_ATTRIBUTES_PARSER, base_parser.SINGLE_INPUT_LAYER_PARSER],
		description="Generate parastichy spirals from a set of nodes.")
	parastichy_parser.add_argument("--prefix", "-P", type=utils.layer_type, default="P",
		help="Prefix used for each layer containing the corresponding parastichy spirals.")

	def arg_validator_parastichy(a):
		"Either a positive number or F<n> where n is the n'th Fibonacci number 0,1,1,2,3... numbered from zero."
		try:
			if a and a[0].upper() == 'F':
				nfib = int(a[1:])
				if nfib < 1:
					raise ValueError
				F = [0,1]
				for i in range(nfib-1):
					F.append(F[-2]+F[-1])
				v =  F[nfib]
			else:
				v = int(a)
				if v < 1:
					raise ValueError
			return v
		except ValueError:
			raise argparse.ArgumentTypeError(f"Parasticy value '{a}' illegal.")
	parastichy_parser.add_argument("--parastichy", "-p", type=arg_validator_parastichy, nargs='+', action='extend',
		help='parastichy number, either a positive integer of the zero based index of a Fibonacci number.')

	@cmd2.with_argparser(parastichy_parser)
	def do_parastichy(self, ns:argparse.Namespace):
		ns.parastichy = list(set(ns.parastichy))			# Get rid of duplicates.
		nodes = self._cmd.dd.get(ns.layer).widget("nodes").items
		self._cmd.dump_args_option(ns)
		if not nodes:
			self._cmd.warn_if_verbose(f"No nodes on layer {ns.layer}.")
		else:
			for ps_num in ns.parastichy:
				self._cmd.pdebug(f"Parastichy number = {ps_num}.")
				nodes_visited = set()
				for c_start in range(len(nodes)-1, -1, -1):
					if c_start not in nodes_visited:
						para_spiral = list(range(c_start, -1, -ps_num))
						if len(para_spiral) > 1:
							nodes_visited.update(para_spiral)
							layer = f"{ns.prefix}{ps_num}"
							self._cmd.dd.get(layer).widget("lines").set([[nodes[x][0:2] for x in para_spiral]], append=True)
							self._cmd.add_layer_attributes(layer, ns)

	# Voronoi cell generator.
	#
	voronoi_parser = cmd2.Cmd2ArgumentParser(
		parents=[base_parser.GENERIC_ATTRIBUTES_PARSER, base_parser.SINGLE_INPUT_LAYER_PARSER, base_parser.OUTPUT_LAYER_PARSER, base_parser.APPEND_OPTION_PARSER],
		description="Generate Voronoi regions from a set of nodes.")

	@cmd2.with_argparser(voronoi_parser)
	def do_voronoi(self, ns:argparse.Namespace):
		self._cmd._update_output_layer(ns, "voronoi")
		self._cmd.dump_args_option(ns)

		seeds = [x[:2] for x in self._cmd.get_data(ns, "nodes")]		# Strip diameter.
		if seeds:
			v = Voronoi(seeds)															# Build Voronoi regions.
			region_indices = [r for r in v.regions if r and -1 not in r]	# Regions as vertex indices, miss out empty/unbounded.
			cells = [[list(map(float, v.vertices[x])) for x in ri] for ri in region_indices]
			self._cmd.warn_if_verbose(f"Generating Voronoi regions from seeds, got {len(cells)} polygons.")
			self._cmd.update_widget_data(ns.output_layer, "cells", cells, append=ns.append)
			self._cmd.add_layer_attributes(ns.output_layer, ns)

	# Mesh command -- generate cells from set of intersecting lines,
	#
	mesh_parser = cmd2.Cmd2ArgumentParser(
		parents=[base_parser.GENERIC_ATTRIBUTES_PARSER, base_parser.MULTI_INPUT_LAYERS_PARSER, base_parser.OUTPUT_LAYER_PARSER, base_parser.APPEND_OPTION_PARSER],
		description="Generate cells from mesh of lines (typically parastichies) on any number of layers.")
	mesh_parser.add_argument("--n-sides", "-n", type=int, default=4,
		help="Number of sides for cells, default is 4, set to < 3 for all.")
	mesh_parser.add_argument("--dump-graph", "-d", action="store_true",
		help="Dump graph as lines of form <node> <neighbours>.")

	@cmd2.with_argparser(mesh_parser)
	def do_mesh(self, ns:argparse.Namespace):
		self._cmd._update_output_layer(ns, "mesh")
		if ns.n_sides < 3:
			ns.n_sides = None
		self._cmd.dump_args_option(ns)

		p_graph = nx.Graph()
		for ll in ns.layers:																				# For each layer...
			for line in self._cmd.dd.get(ll).widget("lines").items:		# For each line (set of points)...
				for i in range(len(line)-1):														# Index over each point from first to next to last...
					p_graph.add_edge(tuple(line[i]), tuple(line[i+1]))		# Add graph edge with (x,y) point as node.
		#print("Nodes:", nodes, len(nodes))
		#print("Edges:", list(p_graph.edges))

		if ns.dump_graph:
			nodes = list(p_graph.nodes)
			for i in range(len(nodes)):
				self._cmd.poutput(i, ' '.join([str(nodes.index(x)) for x in p_graph.neighbors(nodes[i])]))

		raw_cells = nx.simple_cycles(p_graph, ns.n_sides)  # Not sure if this is best function. Seems to work.
		if ns.n_sides:
			raw_cells = [c for c in raw_cells if len(c) == ns.n_sides]
		cells = [[list(p) for p in cc] for cc in raw_cells]
		# print(utils.dump(cells, sigfigs=self._cmd.sigfigs, width=self._cmd.term_width))
		self._cmd.update_widget_data(ns.output_layer, "cells", cells, append=ns.append)
		self._cmd.add_layer_attributes(ns.output_layer, ns)

	# Cell processor command
	#

	# TODO: Overengineered, simple functions would do.
	class BaseCellproc:
		def __init__(self):
			self.cells = []
		def do_process_polygon(self, p:Polygon) -> Polygon:
			raise RuntimeError("Overload in subclass!")
		def process(self, cells:utils.Cells):
			polygons_f = [self.do_process_polygon(utils.cell_to_polygon(cc)) for cc in cells]
			return [utils.polygon_to_cell(p) for p in polygons_f if p]

	class CellprocChop(BaseCellproc):
		"Chop: smoothing filter that removes corners so does not overflow original cell boundary."
		def __init__(self, arg):
			super().__init__()
			self.arg = 3 if arg is None else utils.arg_positive_int(arg)
		def do_process_polygon(self, p:Polygon) -> Polygon:
			return shapelysmooth.chaikin_smooth(p, iters=self.arg)
	class CellprocSpline(BaseCellproc):
		"Spline: smoothing that might overflow original cell boundary."
		def __init__(self, arg):
			super().__init__()
			self.arg = 3 if arg is None else utils.arg_positive_int(arg)
		def do_process_polygon(self, p:Polygon) -> Polygon:
			return shapelysmooth.catmull_rom_smooth(p, alpha=0.5, subdivs=self.arg)
	class CellprocReduceRounded(BaseCellproc):
		"Reducerounded: reduce cell size by offset given and round sharp corners."
		def __init__(self, arg):
			super().__init__()
			self.arg = 1.0 if arg is None else float(arg)
		def do_process_polygon(self, p:Polygon) -> Polygon:
			return p.buffer(-2*self.arg).buffer(self.arg)
	class CellprocReduce(BaseCellproc):
		"Reduce: change cell size by offset given, negative to increase."
		def __init__(self, arg):
			super().__init__()
			self.arg = 1.0 if arg is None else float(arg)
		def do_process_polygon(self, p:Polygon) -> Polygon:
			return p.buffer(-self.arg)
	class CellprocSort:
		"Sort: sort in order of increasing distance to origin."
		def __init__(self, arg):
			pass
		def process(self, cc:utils.Cells) -> utils.Cells:
			pp = []
			for c in cc:
				centroid = utils.cell_to_polygon(c).centroid
				pp.append((math.hypot(centroid.x, centroid.y), c))
			pp.sort(key=lambda ps: ps[0])
			return [p[1] for p in pp]

	#TODO: grab from globals.
	_CELL_FILTERS = CellprocChop, CellprocSpline, CellprocReduceRounded, CellprocReduce, CellprocSort

	_CELL_FILTERS_HELPS = ''.join([f"{it.__doc__}\n" for it in _CELL_FILTERS])
	_CELL_FILTER_CHOICES = {it.__doc__.split(":")[0].lower(): it for it in _CELL_FILTERS}

	cellproc_parser = cmd2.Cmd2ArgumentParser(
		parents=[base_parser.GENERIC_ATTRIBUTES_PARSER, base_parser.SINGLE_INPUT_LAYER_PARSER, base_parser.OUTPUT_LAYER_PARSER],
		description=f"""Process the cells on a single layer.
{_CELL_FILTERS_HELPS}""")
	cellproc_parser.add_argument("--filter", "-f", choices=list(_CELL_FILTER_CHOICES.keys()), required=True, # Required option is bad style!
		help="Various filtering & processing algorithms.")
	cellproc_parser.add_argument("--degree", "-d",
		help="Processor parameter, meaning depends on algorithm.")

	@cmd2.with_argparser(cellproc_parser)
	def do_cellproc(self, ns:argparse.Namespace):
		# TODO: If more than one command rewrites data on a layer make a function.
		if not ns.output_layer:
			if not self._cmd.get_confirmation(f"Processed cells will replace original"):
				return
			ns.output_layer = ns.layer
		self._cmd.dump_args_option(ns)

		if cells := self._cmd.get_data(ns, "cells"):
			cell_filter = self._CELL_FILTER_CHOICES[ns.filter](ns.degree)
			processed_cells = cell_filter.process(cells)
			self._cmd.warn_if_verbose(f"Cell count {len(cells)} -> {len(processed_cells)}.")
			self._cmd.update_widget_data(ns.output_layer, "cells", processed_cells, append=False)
			self._cmd.add_layer_attributes(ns.output_layer, ns)

	# Outline command - generates outline for set of cells.
	#
	outline_parser = cmd2.Cmd2ArgumentParser(
		parents=[base_parser.GENERIC_ATTRIBUTES_PARSER, base_parser.SINGLE_INPUT_LAYER_PARSER, base_parser.OUTPUT_LAYER_PARSER, base_parser.APPEND_OPTION_PARSER],
		description=f"Generate outline cell for all cells on a single layer.")
	outline_parser.add_argument("--border", "-b", type=float, default='0.0',
	 help="border from outer cells to border, can be negative")
	outline_parser.add_argument("--smoothing", "-s", type=utils.ArgValidator(float, lambda x: 0.0 <= x <= 100.0),
		default=3.0,
		help="smoothing applied to border, range 0..100")

	@cmd2.with_argparser(outline_parser)
	def do_outline(self, ns:argparse.Namespace):
		self._cmd._update_output_layer(ns, "outline")
		self._cmd.dump_args_option(ns)

		if cells := self._cmd.get_data(ns, "cells"):
			input_polys = [utils.cell_to_polygon(c).buffer(ns.border) for c in cells]
			gdf = gpd.GeoSeries([unary_union(input_polys)])		# Create a GeoSeries from the combined geometry
			concave_hull_polygon = gdf.concave_hull(ratio=ns.outline_smoothing/100.0)[0]
			self._cmd.update_widget_data(ns.output_layer, "cells", [utils.polygon_to_cell(concave_hull_polygon)], append=False)

	# Centroid command -- add nodes based on centroid of cell.
	#
	centroid_parser = cmd2.Cmd2ArgumentParser(
		parents=[base_parser.GENERIC_ATTRIBUTES_PARSER, base_parser.SINGLE_INPUT_LAYER_PARSER, base_parser.OUTPUT_LAYER_PARSER],
		description=f"Generate centroids for the cells on a single layer.")

	@cmd2.with_argparser(centroid_parser)
	def do_centroid(self, ns:argparse.Namespace):
		self._cmd._update_output_layer(ns, "centroid")
		self._cmd.dump_args_option(ns)

		if cells := self._cmd.get_data(ns, "cells"):
			centroids = [Polygon(cc).centroid for cc in cells]
			node_ex = [ns.diameter] if ns.diameter else []
			self._cmd.update_widget_data(ns.output_layer, "nodes", [[cc.x,cc.y]+node_ex for cc in centroids], append=False)
			self._cmd.add_layer_attributes(ns.output_layer, ns, exclude="diameter")

	# Sort command, sorts data items by coords of midpoint.
	sort_parser = cmd2.Cmd2ArgumentParser(
		parents=[base_parser.GENERIC_ATTRIBUTES_PARSER, base_parser.SINGLE_INPUT_LAYER_PARSER],
		description=f"Sort the data items (nodes, lines, cells) on a single layer. Note that this modifies the data in-place.")
	sort_parser.add_argument("--items", "-i", action='extend', nargs='*', choices=sf2_common.WIDGET_NAMES,
		default=sf2_common.WIDGET_NAMES,
		help="Data items to sort, defaults to all")
	sort_parser.add_argument("--property", "-p", choices='min mid max'.split(), default='mid',
		help="item property to sort by, minimum/maximum magnitude or midpoint")
	sort_parser.add_argument("--reverse", "-r", action='store_true',
		help="Reverse order of sort.")
	@cmd2.with_argparser(sort_parser)
	def do_sort(self, ns:argparse.Namespace):
		self._cmd.dump_args_option(ns)

		for d_key in ns.items:
			ppd = self._cmd.dd.get(ns.layer).widget(d_key).get_item_coords(pos=ns.property)
			#print(ppd)
			pp = [(math.hypot(p[0], p[1]), p) for p in ppd]
			#print(d_key)
			# for p in pp:
				#print(' ', p)
			pp.sort(key=lambda p: p[0])
			if ns.reverse:
				pp.reverse()
			self._cmd.update_widget_data(ns.layer, d_key, [p[1] for p in pp])

		self._cmd.add_layer_attributes(ns.layer, ns)
'''
	# Index command, places index number for data items.
	index_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser.GENERIC_ATTRIBUTES, utils.SINGLE_INPUT_LAYER_PARSER, utils.OUTPUT_LAYER_PARSER],
		description=f"Place text with the index for data items (nodes, lines, cells) on a single layer.")
	index_parser.add_argument("--items", "-i", action='extend', nargs='*',
		help="Data items to process, defaults to all")
	index_parser.add_argument("--position", "-p", choices='min mid max'.split(), default='mid',
		help="text placement, minimum/maximum magnitude or midpoint")
	@cmd2.with_argparser(index_parser)
	def do_index(self, ns:argparse.Namespace):
		self._cmd._update_output_layer("outline")
		if not ns.items:
			ns.items = LayerSet.DATA_KEYS
		self._cmd.dump_args_option(ns)

		ppds = [(d_key, self._cmd.dd.get_data_item_coords(ns.layer, d_key, pos=ns.position)) for d_key in ns.items]
		for d_key, ppd in ppds:																		# Avoid mutating layer we are iterating over.
			print("PPD", d_key, ppd)
			for i, p in enumerate(ppd, 1):
				self._cmd.add_data_to_layer(ns.output_layer, "text", [p[0], p[1], f"{i}"], append=True)

		self._cmd.add_layer_attributes(ns.output_layer, ns)
	'''
