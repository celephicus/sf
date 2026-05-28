from typing import Tuple, List
import argparse, math, time
from pathlib import Path
import json
from itertools import batched			# Very useful, turn sequence or iterator into subsequences.

import tomli_w
import cmd2
from python_tsp.distances import euclidean_distance_matrix
from python_tsp.heuristics import solve_tsp_local_search, solve_tsp_simulated_annealing

import utils, base_parser, sf2_common
from layer_set import LayerSet

@cmd2.with_default_category('Node Commands')
class NodeCommands(cmd2.CommandSet):
	"""Node Generators -- generate clouds of nodes as spirals, rings, etc. Generates a new layer if not existing."""
	def __init__(self):
		super().__init__()

	def add_diameter_from_arg(self, diameter, nodes):
		"Note the --diameter option does not set the layer attribute, it sets the _actual_ diameter of the generated nodes if diameter not already present."
		if diameter:
			nodes[:] = [(p + [diameter]) if len(p) == 2 else p for p in nodes]

	# Command circle: add single circles. Intended for reference circles
	#
	node_circle_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser.OUTPUT_LAYER_PARSER, base_parser.GENERIC_ATTRIBUTES_PARSER],
		description="Add a single node, always appends to existing nodes.")

	def arg_circle_type(a):
		"Either a pair or a triplet of floats."
		try:
			parts = [float(x) for x in a.split(',')]
			assert len(parts) in (2,3)
		except:
			raise argparse.ArgumentTypeError(f"Expected 2 or 3 values, separated by a ','.")
		if len(parts) == 3 and parts[2] <= 0:
			raise argparse.ArgumentTypeError(f"Diameter value must be positive")
		return parts
	node_circle_parser.add_argument("--pos", "-p", type=arg_circle_type, default=[[0.0, 0.0]], nargs='+', action='extend',
		help="Position of circle centre, defaults to origin; third value may be diameter, overrides --diameter option.")

	@cmd2.with_argparser(node_circle_parser)
	def do_circle(self, ns:argparse.Namespace):
		self._cmd.dump_args_option(ns, "Raw args")
		self.add_diameter_from_arg(ns.diameter, ns.pos)
		self._cmd.dump_args_option(ns, "Fixed args")
		self._cmd.update_widget_data(ns.output_layer, "nodes", ns.pos, append=True)
		self._cmd.add_layer_attributes(ns.output_layer, ns, exclude="diameter")

	# Command ring: makes a ring of equally spaced nodes.
	#
	NODE_RING_DEFAULT_OFFSET = 1.50           # Seems to work well for variety of node counts.
	node_ring_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser.OUTPUT_LAYER_PARSER, base_parser.GENERIC_ATTRIBUTES_PARSER],
		description="Add a ring of equally spaced nodes, always appends to existing nodes.")
	node_ring_parser.add_argument("--count", "-n", type=utils.arg_positive_int, default=100, # And a count.
		help="number of nodes")

	node_ring_parser_eg = node_ring_parser.add_mutually_exclusive_group()     # Can either have offset or radius, not both.
	node_ring_parser_eg.add_argument("--offset", "-o", type=float, default=NODE_RING_DEFAULT_OFFSET,
		help=f"Set radius offset from largest node by OFFSET, value {NODE_RING_DEFAULT_OFFSET} if not given. Note can be nagative")
	node_ring_parser_eg.add_argument("--radius", "-r", type=utils.arg_non_negative_float,
		help=f"Set radius to value given.")
	@cmd2.with_argparser(node_ring_parser)
	def do_ring(self, ns:argparse.Namespace):
		self._cmd.dump_args_option(ns)

		# Get max radius for existing nodes.
		# TODO: extend to other data?
		existimg_nodes = self.dd.get(ns.output_layer).widget("nodes").items
		max_r = utils.largest_radius(existimg_nodes)

		# Fix count if not given.
		if not ns.count:                                                          # If seed count zero or default choose one.
			F = 1.3 if len(existimg_nodes) > 50 else 2.0                            # Fudge factor for small n.
			ns.count = max(6, int(F * math.pi * math.sqrt(ns.count) + .5))          # Seems to give a good result.

		# Fix ring radius.
		if not ns.radius:                               # If radius not set add offset to largest radius if existing nodes.
			ns.radius = max_r + ns.offset

		self._cmd.dump_args_option(ns, "Fixed args")
		ring_nodes = [[ns.radius, x/ns.count * 2.0*math.pi] for x in range(ns.count)]
		self.add_diameter_from_arg(ns.diameter, ring_nodes)
		self._cmd.update_widget_data(ns.output_layer, "nodes", utils.to_cartesian(ring_nodes), append=True)
		self._cmd.add_layer_attributes(ns.output_layer, ns, exclude="diameter")

	# Spiral generator parser, used by all spiral subcommands.
	#
	spiral_generator_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser.OUTPUT_LAYER_PARSER, base_parser.GENERIC_ATTRIBUTES_PARSER],
		add_help=False)
	spiral_generator_parser.add_argument("--count", "-n", type=utils.arg_positive_int, default=100, # And a count.
		help="number of nodes")
	spiral_generator_parser.add_argument("--start-index", "-i", type=utils.arg_non_negative_int, default=1,
		help="node index to start with")
	spiral_generator_parser.add_argument("--divergence-angle", "-d", type=float, default=360.0/sf2_common.PHI_2,
		help="angle between successive nodes in degrees, no argument is approx. 137.5°, the Golden Angle.")
	spiral_generator_parser.add_argument("--twist", "-t", type=float, default=1.0,
		help="twist factor, controls how many rotations in spiral, ignored for Archimedean.")
	spiral_generator_parser.add_argument("--append", "-a", action='store_true',
		help="appends nodes to existing nodes, default is to clear existing nodes")

	def _spiral_archimedean(_, ns:argparse.Namespace, i:int):
		"Archimedean: simple spiral where the radius is proportional to the angle."
		theta = i*ns.divergence_angle_radians
		r = i
		return [r, theta]
	def _spiral_sunflower(_, ns:argparse.Namespace, i:int):
		"""Sunflower: radius proportional to square root of angle.
		Scaled so that the first few radii are 0.00, 1.00, 1.42, 1.73, 2.00,..."""
		theta = i*ns.divergence_angle_radians
		r = math.sqrt(ns.twist * i)
		return [r, theta]
	def _spiral_log(_, ns:argparse.Namespace, i:int):
		"""Log: radius proportional to exp(b*angle), b = 1/N where N is number of nodes."""
		theta = i*ns.divergence_angle_radians
		theta_scale = ns.twist / ns.count
		r = math.exp(theta_scale * theta)
		return [r, theta]

	def _spiral_generator(self, ns:argparse.Namespace, gen, default_output_layer):
		self._cmd._update_output_layer(ns, default_output_layer)
		self._cmd.dump_args_option(ns)
		node_indices = [i+ns.start_index for i in range(ns.count)]                      # Indices to nodes.
		ns.divergence_angle_radians = 2.0*math.pi*ns.divergence_angle / 360.0           # We work internally in radians.
		nodes_spiral = [gen(ns, n) for n in node_indices]                                    # Run generator.
		self.add_diameter_from_arg(ns.diameter, nodes_spiral)
		self._cmd.update_widget_data(ns.output_layer, "nodes", utils.to_cartesian(nodes_spiral), append=ns.append)
		self._cmd.add_layer_attributes(ns.output_layer, ns, exclude="diameter")

	# Command logarithmic spiral
	#
	spiral_log_parser = cmd2.Cmd2ArgumentParser(parents=[spiral_generator_parser],
		description="""Generate a logarithmic spiral where the radius increases exponentially.
		Note diameter option sets diameter of each node, not the diameter attribute of the layer.""")
	@cmd2.with_argparser(spiral_log_parser)
	def do_log(self, ns:argparse.Namespace):
		self._spiral_generator(ns, self._spiral_log, "log")

	# Command archimedean spiral
	#
	spiral_archimedean_parser = cmd2.Cmd2ArgumentParser(parents=[spiral_generator_parser],
		description="""Generate an archimedean spiral where the radius increases linearly.
		Note diameter option sets diameter of each node, not the diameter attribute of the layer.""")
	@cmd2.with_argparser(spiral_archimedean_parser)
	def do_archimedean(self, ns:argparse.Namespace):
		self._spiral_generator(ns, self._spiral_archimedean, "archimedean")

	# Command archimedean spiral
	#
	spiral_sunflower_parser = cmd2.Cmd2ArgumentParser(parents=[spiral_generator_parser],
		description="""Generate a Fermat spiral where the radius increases with the square root of the index.
		Note diameter option sets diameter of each node, not the diameter attribute of the layer.""")
	@cmd2.with_argparser(spiral_sunflower_parser)
	def do_sunflower(self, ns:argparse.Namespace):
		self._spiral_generator(ns, self._spiral_sunflower, "sunflower")

	# Command wiring -- generate minimal length path through all nodes.
	#
	wiring_parser = cmd2.Cmd2ArgumentParser(
		parents=[base_parser.GENERIC_ATTRIBUTES_PARSER, base_parser.SINGLE_INPUT_LAYER_PARSER, base_parser.OUTPUT_LAYER_PARSER],
		description="""Generate a single line that goes though all nodes in minimum distance. Aka the
		"Travelling Salesman Problem". It is not perfect, and might generate a few crossings.""")
	wiring_parser.add_argument("--start", "-s", type=utils.arg_percent_or_absolute, default=0.0,
		help="Starting position of line, as index or percent of total.")
	wiring_parser.add_argument("--reverse", "-r", action='store_true',
		help="Count start position from the last nade, rather than the first.")
	wiring_parser.add_argument("--led-map", "-m", type=utils.arg_non_negative_int, nargs='?', default=0,
		help="Generate LED map for WLED, if value given then split into strings of this size.")

	@cmd2.with_argparser(wiring_parser)
	def do_wiring(self, ns):
		self._cmd._update_output_layer(ns, "wiring")
		self._cmd.dump_args_option(ns)

		if nodes := self._cmd.get_data(ns, "nodes"):
			nodes = [n[:2] for n in nodes]
			start = max(len(nodes)-1, int(round(0.5 + ns.start if ns.start >= 0.0 else -ns.start/100.0 * len(nodes))))
			self._cmd.pwarning(f"Start index {start}.")
			start_time = time.time()

			# TODO: Roll node list for start point.
			distances = euclidean_distance_matrix(nodes, nodes)
			wiring_order, _ = solve_tsp_simulated_annealing(distances)		# Gives list of indices.  solve_tsp_local_search
			if ns.reverse:
				wiring_order.reverse()
			self._cmd.pwarning(f"Wiring map took {time.time()-start_time:.1f} secs.")

			def wiring_list(x): 															# Print wiring list.
				return ','.join([str(_) for _ in x])
			'''if ns.wiring:
				for n,s in enumerate(batched(wiring_order, ns.wiring), 1):
					self._cmd.poutput(f"LED wiring string {n}: {wiring_list(s)}")
			else:
			'''
			self._cmd.poutput(f"LED wiring: {wiring_list(wiring_order)}")

			# Make LED map, which maps physical to logical index.
			led_map = [-1]*len(wiring_order)
			for n, x in enumerate(wiring_order):
				led_map[x] = n
			assert len(led_map) == len(wiring_order)
			self._cmd.poutput(f"LED map: {wiring_list(led_map)}")

			self._cmd.update_widget_data(ns.output_layer, "lines", [[nodes[i] for i in wiring_order]], append=False)
			self._cmd.add_layer_attributes(ns.output_layer, ns, exclude="diameter")
