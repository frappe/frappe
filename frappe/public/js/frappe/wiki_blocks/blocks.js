// import blocks
import Paragraph from "../wiki_blocks/paragraph";
import Card from "../wiki_blocks/card";
import Chart from "../wiki_blocks/chart";
import Shortcut from "../wiki_blocks/shortcut";
import Blank from "../wiki_blocks/blank";

// import tunes
import SpacingTune from "../wiki_blocks/spacing_tune";

frappe.provide("frappe.wiki_block");

frappe.wiki_block.blocks = {
	paragraph: Paragraph,
	card: Card,
	chart: Chart,
	shortcut: Shortcut,
	blank: Blank,
};

frappe.wiki_block.tunes = {
	spacing_tune: SpacingTune
};