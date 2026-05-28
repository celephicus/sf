from typing import Tuple, List
import argparse
from pathlib import Path
import json

import tomli_w
import cmd2

import utils, base_parser, sf2_common
from layer_set import LayerSet

@cmd2.with_default_category('File Commands')
class FileCommands(cmd2.CommandSet):
	def __init__(self):
		super().__init__()

	def fixup_file_format(self, formats:List[str], ns:argparse.Namespace) -> bool:
		supplied_file = ns.file
		if not ns.file:
			ns.file = Path(self._cmd.filename)
		ext = ns.file.suffix[1:].lower()
		if ns.format:		# If format supplied then add suffix to filename if it doesn't have one.
			if not ext:
				ns.file = ns.file.with_suffix('.'+ns.format)
		else:																		# No format, try to guess.
			ext = ns.file.suffix[1:].lower()
			if ext not in formats:
				self._cmd.perror(f"Cannot guess format from filename {ns.file}. Give a suffix or specify format.")
				return False
			ns.format = ext
		if supplied_file != ns.file:
			self._cmd.warn_if_verbose(f"Writing file '{ns.file}.")
		return True

	# Export command, one layer or all.
	EXPORT_FORMATS = "toml csv json".split()
	import_export_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser.MULTI_INPUT_LAYERS_PARSER],
		description="Export a set of layers.")
	import_export_parser.add_argument("--format", "-F", choices=EXPORT_FORMATS,
		help='output format')
	import_export_parser.add_argument("--file", "-f", type=Path, default=sf2_common.APPNAME,
		help='output filename')
	import_export_parser.add_argument("--data", "-D", choices=sf2_common.WIDGET_NAMES, nargs='*',
		help='data items to export')

	@utils.exclude_from_undo()
	@cmd2.with_argparser(import_export_parser)
	def do_export(self, ns:argparse.Namespace):
		self._cmd._update_layer_list(ns, action_nonexistent="warn")
		self._cmd.dump_args_option(ns, leader="Raw")
		if self.fixup_file_format(self.EXPORT_FORMATS, ns):
			self._cmd.dump_args_option(ns, leader="Fixed")
			exporter = getattr(self, "_export_"+ns.format)
			exporter(ns)

	def _build_export_dict(self, ns:argparse.Namespace):
		if ns.data:
			self._cmd.warn_if_verbose(f"Data item specifiers ignored for format {ns.format}.")
		dd_for_export = {}
		for ll in ns.layers:
			dd_for_export[ll] = {w_name: self._cmd.dd.get(ll).widget(w_name).items for w_name in sf2_common.WIDGET_NAMES}
		return dd_for_export

	def _export_json(self, ns:argparse.Namespace):
		with open(ns.file, 'w') as f:
			json.dump(self._build_export_dict(ns), f)

	def _export_toml(self, ns:argparse.Namespace):
		with open(ns.file, 'wb') as f:
			tomli_w.dump(self._build_export_dict(ns), f)

	def _export_csv(self, ns:argparse.Namespace):
		if len(ns.layers) != 1:
			self._cmd.perror(f"Cannot export CSV data for more than one layer.")
			return
		layer = self._cmd.dd.get(ns.layers[0])

		supplied_data = ns.data
		if not ns.data:
			ns.data = self.dd.WIDGET_NAMES
		data_items = [x for x in ns.data if x in layer.widgets()]
		if not len(data_items):
			self.perror(f"No data item to export.")
			return
		elif len(data_items) > 1:
			self._cmd.perror(f"Multiple data items: '{data_items}' specified.")
			return
		data_k = data_items[0]

		if supplied_data != [data_k]:
			self._cmd.warn_if_verbose(f"Writing data item '{data_k}'.")

		with open(ns.file, 'w', newline='') as file:
			writer = csv.writer(file)
			data_item = layer.widget(data_k).items
			if data_k == 'nodes':
				writer.writerow("X Y Diameter".split())
				for pt in data_item:
					assert len(pt) in (2, 3)
					writer.writerow(pt)
			else:
				assert data_k in "cells lines".split()
				writer.writerow("X Y".split())
				for cell_line in data_item:
					for pt in cell_line:
						assert len(pt) == 2
						writer.writerow(pt)
					writer.writerow([])

	# Plot command.
	#
	plot_parser = cmd2.Cmd2ArgumentParser(parents=[base_parser.MULTI_INPUT_LAYERS_PARSER],
		description="Render a set of layers to a vector graphic file.")
	plot_parser.add_argument("--format", "-F", choices=LayerSet.PLOT_FORMATS,
		help='output format')
	plot_parser.add_argument("--file", "-f", type=Path,
		help='output filename')

	@utils.exclude_from_undo()
	@cmd2.with_argparser(plot_parser)
	def do_plot(self, ns:argparse.Namespace):
		self._cmd._update_layer_list(ns, action_nonexistent="warn")
		self._cmd.dump_args_option(ns, leader="Raw")
		if self.fixup_file_format(LayerSet.PLOT_FORMATS, ns):
			self._cmd.dump_args_option(ns, leader="Fixed")
			plotter = getattr(self, "_plot_"+ns.format)
			plotter(ns)

	def _plot_svg(self, ns:argparse.Namespace) -> None:
		self._cmd.dd.plot_svg(ns.file, ns.layers)
	def _plot_dxf(self, ns:argparse.Namespace) -> None:
		self._cmd.pwarning("Dxf not done yet!")

