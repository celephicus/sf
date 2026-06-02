#!/usr/bin/env python3

import sys, pprint, math, re, argparse, shutil, json, csv, copy, os
from pathlib import Path
from typing import Tuple, List
from collections import deque

import cmd2
from PIL import ImageColor

import utils, base_parser, sf_common, layer_set
import file_commands, cell_commands, node_commands, utility_commands, text_commands

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
		if func and getattr(func, "allow-undo", None):
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
				#try:
					layer.set_attr(attr, val)
				#except Exception as exc:
				#	self.perror(f"Error setting attribute {attr} to {val} for layer {layer_name}: {exc}.")

	def debug_dump(self, leader, stuff):
		"Generic dumper for debug info"
		if self.debug:
			self.ppaged(utils.dump(stuff, leader=leader, sigfigs=self.sigfigs, width=self.term_width))

	def _update_layer_list(self, ns:argparse.Namespace, action_nonexistent:str|None=None) -> None:
		"""Update a list of layers from a user spec that removes duplicates and nonexistent layers and sorts the layers in
		the order that they are in the user data. Also expands wildcards with glob syntax."""
		#TODO: Normalise case of layer names.
		if not ns.layers:                                 # If not given get them all, these will be in the correct order.
			ns.layers = self.dd.layer_names()
		else:
			self.pdebug(f"Raw layers: {ns.layers!r}")
			l_known, l_unknown = utils.expand_items(self.dd.layer_names(), ns.layers)
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


	# Undo & redo commands.
	#

	@cmd2.with_category("history & undo")
	def do_undo(self, ns:argparse.Namespace):
		if self.undo:
			if self.get_confirmation(f"Undo result of command '{self.undo[-1][0]}'."):
				cmd, dd = self.undo.pop()
				self.redo.append((cmd, dd))
				self.warn_if_verbose(f"Undoing result of command '{cmd}'.")
				self.dd = dd
		else:
			self.perror("No items to undo.")

	@cmd2.with_category("history & undo")
	def do_redo(self, ns:argparse.Namespace):
		if self.redo:
			if self.get_confirmation(f"REDO result of command '{self.undo[-1][0]}'."):
				cmd, dd = self.redo.pop()
				self.undo.append((cmd, dd))
				self.warn_if_verbose(f"REDOING result of command '{cmd}'.")
				self.dd = dd
		else:
			self.perror("No items to redo.")

	@cmd2.with_category("history & undo")
	def do_history(self, ns:argparse.Namespace):
		self.poutput("Undo buffer:")
		for s in self.undo:
			self.poutput(f"{s[0]}")
		self.poutput("Redo buffer:")
		for s in self.redo:
			self.poutput(f"{s[0]}")

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
