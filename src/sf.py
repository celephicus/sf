#!/usr/bin/env python3

import sys, pprint, math, re, argparse, shutil, json, csv, copy, os
from pathlib import Path
from typing import Tuple, List
from collections import deque

import cmd2
from PIL import ImageColor
#TODO: Sort out colours.

import utils, base_parser, sf_common, layer_set
import file_commands, cell_commands, node_commands

class SF_App(cmd2.Cmd):
	"""The app."""

	BANNER = f"""\
{sf_common.APPNAME} - a little language for generating patterns inspired by phyllotactic growth.
Type "?" for help.
"""

	UNDO_DEPTH = 4                                # How many edits to undo?

	def __init__(self, sf2_args):
		super().__init__(
			persistent_history_file=f"~/{sf_common.APPNAME}_history",
			startup_script=sf2_args.rc_file,
			intro=self.BANNER,
			suggest_similar_command=True,
			auto_load_commands=True,
			allow_cli_args = False
		)

		self.dd = layer_set.LayerSet(layer_set.Layer(None, sf_common.ATTRIBUTES, sf_common.WIDGETS))		# User data store.

		self.prompt = f"{sf_common.APPNAME}> "       # Show this as the prompt when asking for input.
		self.continuation_prompt = '... '             # Used as prompt for multiline commands after the first line.
		self.default_category = 'Built-in Commands'   # Set the default category name.
		self.onecmd_plus_hooks('alias create q quit') # Handy shortcut.

		# Custom settings
		self.verbose = sf2_args.verbose
		self.add_settable(cmd2.Settable('verbose', bool, "enable more verbose outputs from commands", self))
		self.term_width = shutil.get_terminal_size().columns
		self.add_settable(cmd2.Settable('term_width', int, 'terminal width in characters, used for pretty-printing', self))
		self.query_overwrite = True
		self.add_settable(cmd2.Settable('query_overwrite', bool, 'query before overwriting existing data on a layer', self))
		self.sigfigs = 2
		self.add_settable(cmd2.Settable('sigfigs', int, 'number of digits after d.p for dump', self))
		self.filename = Path(f"{sf_common.APPNAME}.svg")
		self.add_settable(cmd2.Settable('filename', Path, 'default filename for plot', self))

		# Builtin settings.
		self.debug = sf2_args.debug

		self.register_postparsing_hook(self.postparsing_h)      # Called after parsing just before command function.
		self.confirmation = None                              # We only ask for confirmation of overwrite ONCE per command.
		self.register_postcmd_hook(self.postcmd_h)

		self.undo = deque(maxlen=self.UNDO_DEPTH)                                         # Undo queue.
		self.redo = deque(maxlen=self.UNDO_DEPTH)                                         # Undo queue.
		self.add_to_undo("init")

		if sf2_args.rc_file:
			self.warn_if_verbose(f"Loading rc file '{sf2_args.rc_file}'")
		if sf2_args.script:
			self.warn_if_verbose(f"Loading script file '{sf2_args.script}'")
			self.onecmd_plus_hooks(f"run_script {cmd2.string_utils.quote(sf2_args.script)}")

	def add_to_undo(self, cmd:str):
		func = getattr(self, 'do_'+cmd.split()[0], None)
		if func and not getattr(func, "no_undo", None):
			self.undo.append((cmd, copy.deepcopy(self.dd)))
		#print([x[0] for x in self.undo])

	def postparsing_h(self, stuff: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
		self.confirmation = None
		self.add_to_undo(stuff.statement.raw)
		return stuff

	def postcmd_h(self, stuff: cmd2.plugin.PostcommandData) -> cmd2.plugin.PostcommandData:
		#TODO: Easier way to stop auto plot and maybe set formats.
		if self.filename:
			self.pdebug("Autoplot!")
			self.dd.plot_svg(self.filename)			# Do autoplot.
		return stuff

	def get_confirmation(self, prompt):
		"Ask user for confirmation if interactive and we have not asked already for this command."
		if self.confirmation is None:
			if not self.stdin.isatty():       # Are we interactive?
				self.confirmation = True
			else:
				resp = input(f"{prompt} Type 'y' <return> to confirm. ").lower()
				self.confirmation = resp in "y yes".split()
		return self.confirmation

	def warn_if_verbose(self, msg:str):
		if self.verbose:
			self.pwarning(msg)
	def pdebug(self, msg):
		if self.debug:
			self.pwarning(msg)

	def get_data(self, ns, w_name):
		"Convenience method to get widget data from a layer and nag if none found."
		data = self.dd.get(ns.layer).widget(w_name).items
		if not data:
			self.warn_if_verbose(f"Layer '{ns.layer}' has no {w_name} to process.")
		return data

	def update_widget_data(self, layer_name, w_key, data, append=False):
		"""Called to update widget dat on a layer. Will ask for confirmation if data exists and nag if verbose."""
		widget = self.dd.get(layer_name).widget(w_key)
		if not append and widget:
			if self.query_overwrite:
				if not self.get_confirmation(f"Overwrite existing widget data for {w_key} on layer {layer_name}?"):
					return
				self.warn_if_verbose(f"overwriting existing widget data for {w_key} on layer {layer_name}")
		widget.set(data, append=append)

	def _update_output_layer(self, ns, default_layer_name):
		if not ns.output_layer:
			ns.output_layer = default_layer_name
			self.warn_if_verbose(f"Defaulting output layer to '{ns.output_layer}'.")

	#TODO: do this properly with a decorator.
	def dump_args_option(self, ns:argparse.Namespace, leader=None) -> None:
		"Helper to dump args."
		if self.debug:
			self.pwarning(utils.dump_custom_options(ns, leader))

	def add_layer_attributes(self, layer_name:str, ns:argparse.Namespace, exclude:str='') -> None:
		"""Set any layer attributes to layer data."""
		layer = self.dd.get(layer_name)
		for attr in [x for x in layer.ATTRIBUTE_NAMES if x not in exclude.split()]:
			val = getattr(ns, attr, base_parser.NOTSET)
			if val is not base_parser.NOTSET:
				try:
					layer.set_attr(attr, val)
				except Exception:
					self.perror(f"Error setting attribute {attr} to {val} for layer {layer_name}.")

	def debug_dump(self, leader, stuff):
		"Generic dumper for debug info"
		if self.debug:
			self.ppaged(utils.dump(stuff, leader=leader, sigfigs=self.sigfigs, width=self.term_width))

	COMMANDS_UTILITY = "Utility Commands"

	# Utility Commands.
	#

	def _update_layer_list(self, ns:argparse.Namespace, action_nonexistent:str|None=None) -> None:
		"""Update a list of layers from a user spec that removes duplicates and nonexistent layers and sorts the layers in
		the order that they are in the user data."""
		#TODO: Normalise case of layer names & allow wildcards.
		if not ns.layers:                                 # If not given get them all, these will be in the correct order.
			ns.layers = self.dd.ALL_LAYERS
		else:
			self.pdebug(f"Raw layers: {ns.layers!r}")
			raw_layers = sum(map(str.split, ns.layers), [])  # Items in the layers arg may have spaces if they have been quoted.
			raw_layers = [x for x in raw_layers if x.strip()]        # Only want strings with non-blanks.
			l_known, l_unknown = [], []
			for l in raw_layers:
				(l_known if l in self.dd.ALL_LAYERS else l_unknown).append(l)
			if not action_nonexistent or action_nonexistent == 'warn':
				self.warn_if_verbose(f"Unknown layers {','.join(l_unknown)} ignored.")
				ns.layers = l_known
				return True
			elif action_nonexistent == 'keep':
				ns.layers = l_known + l_unknown
				return True
			elif action_nonexistent == 'error':
				return l_unknown
			else:
				raise RuntimeError(f"action_nonexistent must be set to warn (default), keep or error)")


	# Dump command.
	#
	dump_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser.MULTI_INPUT_LAYERS_PARSER],
		description="Dump the data for a selected layer or all layers.")
	dump_parser.add_argument("--summary", "-s", action='store_true',
		help='print summary only')

	@utils.exclude_from_undo()
	@cmd2.with_category(COMMANDS_UTILITY)
	@cmd2.with_argparser(dump_parser)
	def do_dump(self, ns:argparse.Namespace):
		"""Dump requested layers."""
		self._update_layer_list(ns, action_nonexistent="warn")
		self.dump_args_option(ns)
		self.ppaged(self.dd.dump(layer_names=ns.layers, summary=ns.summary, sigfigs=self.sigfigs, width=self.term_width))

	# Undo & redo commands.
	#

	@utils.exclude_from_undo()
	@cmd2.with_category(COMMANDS_UTILITY)
	def do_undo(self, ns:argparse.Namespace):
		if self.undo:
			if self.get_confirmation(f"Undo result of command '{self.undo[-1][0]}'."):
				cmd, dd = self.undo.pop()
				self.redo.append((cmd, dd))
				self.warn_if_verbose(f"Undoing result of command '{cmd}'.")
				self.dd = dd
		else:
			self.perror("No items to undo.")

	@utils.exclude_from_undo()
	@cmd2.with_category(COMMANDS_UTILITY)
	def do_redo(self, ns:argparse.Namespace):
		if self.redo:
			if self.get_confirmation(f"REDO result of command '{self.undo[-1][0]}'."):
				cmd, dd = self.redo.pop()
				self.undo.append((cmd, dd))
				self.warn_if_verbose(f"REDOING result of command '{cmd}'.")
				self.dd = dd
		else:
			self.perror("No items to redo.")

	@utils.exclude_from_undo()
	@cmd2.with_category(COMMANDS_UTILITY)
	def do_history(self, ns:argparse.Namespace):
		self.poutput("Undo buffer:")
		for s in self.undo:
			self.poutput(f"{s[0]}")
		self.poutput("Redo buffer:")
		for s in self.redo:
			self.poutput(f"{s[0]}")

	# Attribute command -- set/clear attributes on layers or defaults.
	attr_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser.MULTI_INPUT_LAYERS_PARSER, base_parser.GENERIC_ATTRIBUTES_PARSER],
		description="Delete or modify/set attributes for a set of layers.")
	attr_parser.add_argument("--default", "-d", action='store_true',
		help="Add attributes used as defaults if not set in layer.")
	@cmd2.with_category(COMMANDS_UTILITY)
	@cmd2.with_argparser(attr_parser)
	def do_attr(self, ns:argparse.Namespace):
		if not ns.default:
			self._update_layer_list(ns, action_nonexistent="keep")
		self.dump_args_option(ns)

		if ns.layers:
			if ns.default:
				self.perror("Cannot set attributes on layers and defaults at same time.")
			else:
				for ll in ns.layers:
					self.add_layer_attributes(ll, ns)
		else:
			if ns.default:
				self.add_layer_attributes(self.dd.PROTO_LAYER_NAME, ns)
			else:
				self.pwarning("No layers or -default specified.")

	# Layer command. All must have some layers specified.
	#  no options, add attributes, e.g. --width=3.
	#  --delete -d --- delete layers, any attribute options are errors.
	#  --remove <k> -- remove attributes or data. If --count if given remove first n, if negative last n.
	#  --trim <k> -- remove attributes or data. If --count if given reduce size to first n, if negative last n.
	#  --strip-diameter --- remove individual diameters from nodes.
	#

	layer_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser.MULTI_INPUT_LAYERS_PARSER], #, base_parser.GENERIC_ATTRIBUTES_PARSER],
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

	@cmd2.with_category(COMMANDS_UTILITY)
	@cmd2.with_argparser(layer_parser)
	def do_layer(self, ns:argparse.Namespace):
		layer_error = self._update_layer_list(ns, action_nonexistent="error")
		self.dump_args_option(ns)
		if layer_error:
			self.perror(f"Nonexistent layer(s): {','.join(layer_error)}.")
			return
		if not ns.layers:
			self.warn_if_verbose("No layers specified.")

		def warn_count():
			if ns.count or ns.reverse:
				self.warn_if_verbose("count/reverse option ignored.")
		def warn_attribute():
			if any([getattr(ns, attr, None) for attr in sf_common.ATTRIBUTE_NAMES]):
				self.warn_if_verbose("Attribute options ignored.")

		if ns.delete:     # Delete entire layer.
			warn_count()
			warn_attribute()
			if not self.get_confirmation(f"Delete layers: {','.join(ns.layers)}."):
					self.poutput("No action.")
					return
			for layer_name in ns.layers:
				self.dd.delete_layer(layer_name)
		elif ns.strip_diameter:     # Remove diameter from nodes.
			warn_count()
			warn_attribute()
			for layer_name in ns.layers:
				self.dd.get(layer_name).transform_item_coords(lambda p: p[:2], ["nodes"])
		elif ns.remove:           # Remove attributes or widgets
			for layer_name in ns.layers:
				layer = self.dd.get(layer_name)
				for prop in ns.remove:		# Might be attribute or widget name.
					if attr in self.dd.ATTRIBUTE_NAMES:
						layer.set_attr(attr, None)
					else:
						assert attr in self.dd.WIDGET_NAMES		# The arg parser should make sure of this.
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
	rescale_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser.MULTI_INPUT_LAYERS_PARSER],
		description="Rescale a set of layers to ft the extents of the data items.")

	rescale_parser_eg = rescale_parser.add_mutually_exclusive_group()
	rescale_parser_eg.add_argument("--fit", "-f", type=utils.arg_positive_float, default=500.0,
		help='scale all items to fit within square of given side')
	rescale_parser_eg.add_argument("--scale", "-s", type=utils.arg_positive_float,
		help='scale all items')

	rescale_parser.add_argument("--border", "-b", type=utils.arg_percent_or_absolute, default=5.0,
		help='border, either in mm or as a percentage of the extents')
	@cmd2.with_category(COMMANDS_UTILITY)
	@cmd2.with_argparser(rescale_parser)
	def do_rescale(self, ns:argparse.Namespace):
		self._update_layer_list(ns)
		self.dump_args_option(ns)
		'''
		extents = utils.Extents()               # Compute extents as we will probably need it.
		for layer_name in ns.layers:
			self.dd.get(layer_name).update_extents_widgets(extents)
		max_orth_dist = max(sum(extents.get(), []))
		self.pdebug(f"Extents for layers {ns.layers}: {extents} maxsize={extents.max_size()} {max_orth_dist}")
		if not extents:
			self.warn_if_verbose("No data found to scale.")
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
			self.dd.get(layer_name).foreach_coord(lambda pt,d: d.update(pt), max_dist)
		self.pdebug(f"Max ortho dist = {max_dist.get()}")

		if ns.scale:                            # Either scale or fit.
			scale = ns.scale
		else:
			border = ns.border if ns.border >= 0.0 else max_dist.get() *-ns.border/100.0 # Add border as val or percent of extents.
			scale = (ns.fit/2 - border) / max_dist.get()
			self.pdebug(f"Fitting: scale: scale={scale} border={border}")
		for layer_name in ns.layers:
			self.dd.get(layer_name).transform_item_coords(lambda pt: [pt[0]*scale, pt[1]*scale] + pt[2:])

		max_dist = MaxOrthoDist()
		for layer_name in ns.layers:
			self.dd.get(layer_name).foreach_coord(lambda pt,d: d.update(pt), max_dist)
		self.pdebug(f"Max ortho dist = {max_dist.get()}")

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--verbose', '-v', action='store_true', help='enable verbose output')
	parser.add_argument('--debug', '-d', action='store_true', help='enable debug mode')
	parser.add_argument("script", type=str, nargs='?', help="Run user script(s) on startup.")
	parser.add_argument("--no-rc", "-n", action="store_true",
		help="Do not run f{sf_common.APPNAME}")
	sf2_args = parser.parse_args()

	# The rc file for sf2 is read from ~/.sf2_rc or .sf2_rc
	SF2_RC = f"{sf_common.APPNAME}_rc"		# File to run at startup
	SF2_RC_PATHS = SF2_RC, os.path.expanduser("~/"+SF2_RC)
	sf2_args.rc_file = None
	if not sf2_args.no_rc:
		for f in SF2_RC_PATHS:
			if os.path.exists(f):
				sf2_args.rc_file = f
				break

	print(sf2_args)
	sf_app = SF_App(sf2_args)
	sys.exit(sf_app.cmdloop())
