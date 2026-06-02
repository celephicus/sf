import argparse

import cmd2

import utils, base_parser, sf_common

@cmd2.with_default_category('Text Commands')
class TextCommands(cmd2.CommandSet, base_parser.Parsers):
	"""Some commands for adding text."""
	def __init__(self):
		super().__init__()

	# Index command, places index number for data items.
	index_parser = cmd2.Cmd2ArgumentParser(
		parents=[base_parser.GENERIC_ATTRIBUTES_PARSER, base_parser.Parsers.SINGLE_INPUT_LAYER_PARSER, base_parser.Parsers.OUTPUT_LAYER_PARSER],
		description=f"Place text with the index for data items (nodes, lines, cells) on a single layer.")
	index_parser.add_argument("--items", "-i", action='extend', nargs='*', choices=sf_common.WIDGET_NAMES,
		help="Data items to process, defaults to all")
	index_parser.add_argument("--position", "-p", choices='min mid max'.split(), default='mid',
		help="text placement, minimum/maximum magnitude or midpoint")
	@cmd2.with_argparser(index_parser)
	@utils.add_func_attr("allow-undo")
	def do_index(self, ns:argparse.Namespace):
		self._cmd._update_output_layer(ns, "index")
		if not ns.items:
			ns.items = sf_common.WIDGET_NAMES
		self._cmd.dump_args_option(ns)

		for d_key in ns.items:
			ppd = self._cmd.dd.get(ns.layer).widget(d_key).get_item_coords(pos=ns.position)
			print(f"{d_key}: {ppd}")
			for i, xy in enumerate(ppd, 1):
				self._cmd.update_widget_data(ns.output_layer, "text", [[xy[0], xy[1], f"{i}"]], append=True)

		self._cmd.add_layer_attributes(ns.output_layer, ns)

