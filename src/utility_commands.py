import argparse

import cmd2

import utils, base_parser, sf_common, layer_set

@cmd2.with_default_category('Utility Commands')
class UtilityCommands(cmd2.CommandSet, base_parser.Parsers):
	"""Some utility commands."""
	def __init__(self):
		super().__init__()

	# Dump command.
	#
	dump_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser.Parsers.MULTI_INPUT_LAYERS_PARSER],
		description="Dump the data for a selected layer or all layers.")
	dump_parser.add_argument("--summary", "-s", action='store_true',
		help='print summary only')

	@cmd2.with_argparser(dump_parser)
	def do_dump(self, ns:argparse.Namespace):
		"""Dump requested layers."""
		self._cmd._update_layer_list(ns, action_nonexistent="warn")
		self._cmd.dump_args_option(ns)
		self._cmd.ppaged(self._cmd.dd.dump(layer_names=ns.layers, summary=ns.summary, sigfigs=self._cmd.sigfigs, width=self._cmd.term_width))


	# Attribute command -- set/clear attributes on layers or defaults.
	attr_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser.Parsers.MULTI_INPUT_LAYERS_PARSER, base_parser.GENERIC_ATTRIBUTES_PARSER],
		description="Delete or modify/set attributes for a set of layers.")
	attr_parser.add_argument("--default", "-d", action='store_true',
		help="Add attributes used as defaults if not set in layer.")
	@utils.add_func_attr("allow-undo")
	@cmd2.with_argparser(attr_parser)
	def do_attr(self, ns:argparse.Namespace):
		if not ns.default:
			self._cmd._update_layer_list(ns, action_nonexistent="keep")
		self._cmd.dump_args_option(ns)

		if ns.layers:
			if ns.default:
				self._cmd.perror("Cannot set attributes on layers and defaults at same time.")
			else:
				for ll in ns.layers:
					self._cmd.add_layer_attributes(ll, ns)
		else:
			if ns.default:
				self._cmd.add_layer_attributes(self._cmd.dd.PROTO_LAYER_NAME, ns)
			else:
				self._cmd.pwarning("No layers or -default specified.")

	# Layer command. All must have some layers specified.
	#  no options, add attributes, e.g. --width=3.
	#  --delete -d --- delete layers, any attribute options are errors.
	#  --remove <k> -- remove attributes or data. If --count if given remove first n, if negative last n.
	#  --trim <k> -- remove attributes or data. If --count if given reduce size to first n, if negative last n.
	#  --strip-diameter --- remove individual diameters from nodes.
	#

	layer_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser.Parsers.MULTI_INPUT_LAYERS_PARSER], #, base_parser.GENERIC_ATTRIBUTES_PARSER],
		description="Delete or modify/set attributes for a set of *existing* layers.")
	layer_parser.add_argument("--count", "-n", type=int,
		help='number of items, if positive remove first n or if negative leave first n')
	layer_parser.add_argument("--reverse", "-R", action='store_true',
		help="Make the remove option count from the END, not the START.")

	layer_parser_eg = layer_parser.add_mutually_exclusive_group()
	layer_parser_eg.add_argument("--strip-diameter", "-s", action='store_true',
		help='Strip explicit diameter from nodes items.')
	layer_parser_eg.add_argument("--delete", "-d", action='store_true',
		help='Delete entire layer.')
	layer_parser_eg.add_argument("--remove", "-r", choices=sf_common.ATTRIBUTE_NAMES+sf_common.WIDGET_NAMES,
		action='extend', nargs='+',
		help="Remove attributes or data. If --count=<n> if given reduce items to first n, if negative last n.")

	@cmd2.with_argparser(layer_parser)
	@utils.add_func_attr("allow-undo")
	def do_layer(self, ns:argparse.Namespace):
		layer_error = self._cmd._update_layer_list(ns, action_nonexistent="error")
		self._cmd.dump_args_option(ns)
		if layer_error:
			self._cmd.perror(f"Nonexistent layer(s): {','.join(layer_error)}.")
			return
		if not ns.layers:
			self._cmd.warn_if_verbose("No layers specified.")

		def warn_count():
			if ns.count or ns.reverse:
				self._cmd.warn_if_verbose("count/reverse option ignored.")
		def warn_attribute():
			if any([getattr(ns, attr, None) for attr in sf_common.ATTRIBUTE_NAMES]):
				self._cmd.warn_if_verbose("Attribute options ignored.")

		if ns.delete:     # Delete entire layer.
			warn_count()
			warn_attribute()
			if not self._cmd.get_confirmation(f"Delete layers: {','.join(ns.layers)}."):
					self._cmd.poutput("No action.")
					return
			for layer_name in ns.layers:
				self._cmd.dd.delete_layer(layer_name)
		elif ns.strip_diameter:     # Remove diameter from nodes.
			warn_count()
			warn_attribute()
			for layer_name in ns.layers:
				self._cmd.dd.get(layer_name).transform_item_coords(lambda p: p[:2], ["nodes"])
		elif ns.remove:           # Remove attributes or widgets
			for layer_name in ns.layers:
				layer = self._cmd.dd.get(layer_name)
				for prop in ns.remove:		# Might be attribute or widget name.
					if attr in self._cmd.dd.ATTRIBUTE_NAMES:
						layer.set_attr(attr, None)
					else:
						assert attr in self._cmd.dd.WIDGET_NAMES		# The arg parser should make sure of this.
						widget = layer.widget(attr)
						if ns.count > 0:
							if not ns.reverse:
								del widget.items[:ns.count]    									# Remove FIRST n items.
							else:
								del widget.items[-ns.count:]    								# Remove LAST n items.
						elif ns.count < 0:
							if not ns.reverse:
								del widget.items[:len(widget.items)-ns.count]		# Trim to n items be removing from START.
							else:
								del widget.items[len(widget.items)-ns.count:]		# Trim to n items be removing from END.
						else:
							layer.widget.clear()
		else:
			raise RuntimeError("Expected some action to do!")

	# Scale command
	#
	rescale_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser.Parsers.MULTI_INPUT_LAYERS_PARSER],
		description="Rescale a set of layers to ft the extents of the data items.")

	rescale_parser_eg = rescale_parser.add_mutually_exclusive_group()
	rescale_parser_eg.add_argument("--fit", "-f", type=utils.arg_positive_float, default=500.0,
		help='scale all items to fit within square of given side')
	rescale_parser_eg.add_argument("--scale", "-s", type=utils.arg_positive_float,
		help='scale all items')

	rescale_parser.add_argument("--border", "-b", type=utils.arg_percent_or_absolute, default=5.0,
		help='border, either in mm or as a percentage of the extents')
	@cmd2.with_argparser(rescale_parser)
	@utils.add_func_attr("allow-undo")
	def do_rescale(self, ns:argparse.Namespace):
		self._cmd._update_layer_list(ns)
		self._cmd.dump_args_option(ns)
		'''
		extents = utils.Extents()               # Compute extents as we will probably need it.
		for layer_name in ns.layers:
			self._cmd.dd.get(layer_name).update_extents_widgets(extents)
		max_orth_dist = max(sum(extents.get(), []))
		self._cmd.pdebug(f"Extents for layers {ns.layers}: {extents} maxsize={extents.max_size()} {max_orth_dist}")
		if not extents:
			self._cmd.warn_if_verbose("No data found to scale.")
			return
		'''
		class MaxOrthoDist:
			def __init__(self):
				self.d = 0.0
			def update(self, pt):
				self.d = max(self.d, abs(pt[0]), abs(pt[1]))
			def get(self):
				return self.d
		max_dist = MaxOrthoDist()
		for layer_name in ns.layers:
			self._cmd.dd.get(layer_name).foreach_coord(lambda pt,d: d.update(pt), max_dist)
		self._cmd.pdebug(f"Max ortho dist = {max_dist.get()}")

		if ns.scale:                            # Either scale or fit.
			scale = ns.scale
		else:
			border = ns.border if ns.border >= 0.0 else max_dist.get() *-ns.border/100.0 # Add border as val or percent of extents.
			scale = (ns.fit/2 - border) / max_dist.get()
			self._cmd.pdebug(f"Fitting: scale: scale={scale} border={border}")
		for layer_name in ns.layers:
			self._cmd.dd.get(layer_name).transform_item_coords(lambda pt: [pt[0]*scale, pt[1]*scale] + pt[2:])

		max_dist = MaxOrthoDist()
		for layer_name in ns.layers:
			self._cmd.dd.get(layer_name).foreach_coord(lambda pt,d: d.update(pt), max_dist)
		self._cmd.pdebug(f"Max ortho dist = {max_dist.get()}")
