#!/usr/bin/env python3

from shapely.geometry import Polygon

import matplotlib.pyplot as plt
import shapelysmooth

parser.add_argument("--text-height", "-T", type=float, default=2.0,
	help="text height for notes on output")

# Wiring order generation.
parser.add_argument("--wiring", "-w", type=int, nargs='?', metavar='N', default=None, const=0,
	help="generate wiring order, broken into strings if number given")
parser.add_argument("--wiring-reverse", "-r", action="store_true", default=False, help="reverse wiring order")
parser.add_argument("--wiring-start", type=str, default='0', help="first seed, either index or percent of total")

# Parse args and do some post-processing then dump.
args = parser.parse_args()
message.set_verbosity(args.verbosity)
message.set_leader("{elapsed:.3f}: [{level}] ")

if args.boundary_seed_count <= 0:																			# If seed count zero or default choose one.
	F = 1.3 if args.node_count > 50 else 2.0														# Fudge factor for small n.
	args.boundary_seed_count = int(F * math.pi * math.sqrt(args.node_count) + .5)   # Seems to give a good result.

# Compute wiring start index; can't be done by an argparse type conversion function as the node count may not be known.
try:
	if args.wiring_start.endswith('%'):
		wsi = int(round(float(args.wiring_start[:-1])/100.0 * args.node_count))
	else:
		wsi = int(args.wiring_start)
except ValueError:
	sys.exit(f"Bad value for wiring start, expect number or percentage.")
args.wiring_start = min(args.node_count-1, max(0, wsi))		# Clip to sensible limits.

# Generate wiring list for LEDs that minimises wire length.
wiring_order = []
if args.wiring is not None:
	if not cells:
		message.warn("Cannot generate wiring order as no cells found.")
	else:
		from greedy import solve_tsp 			# From https://github.com/dmishin/tsp-solver, pip has version with no endpoints.
		from itertools import batched			# Very useful, turn sequence or iterator into subsequences.
		start_time = time.time()

		pp = list(zip(*cells))[I_CENTROID]		# List of coords of centroids of the polygons.
		wiring_order = solve_tsp([[math.dist(a,_) for _ in pp] for a in pp], endpoints=(args.wiring_start,None))
		if args.wiring_reverse:
			wiring_order.reverse()
		message.info(f"Wiring map took {time.time()-start_time:.1f} secs.")

		def wiring_list(x): 																			# Print wiring list.
			return ','.join([str(_) for _ in x])
		if args.wiring:
			for n,s in enumerate(batched(wiring_order, args.wiring), 1):
				print(f"LED wiring string {n}: {wiring_list(s)}")
		else:
			print(f"LED wiring: {wiring_list(wiring_order)}")

		# Make LED map, which maps physical to logical index.
		led_map = [-1]*len(wiring_order)
		for n,x in enumerate(wiring_order):
			led_map[x] = n
		assert len(led_map) == len(wiring_order)
		print(f"LED map:    {wiring_list(led_map)}")

