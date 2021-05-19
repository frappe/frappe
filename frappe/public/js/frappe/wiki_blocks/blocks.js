// import blocks
import Header from "../wiki_blocks/header";
import Paragraph from "../wiki_blocks/paragraph";
import Card from "../wiki_blocks/card";
import Chart from "../wiki_blocks/chart";
import Shortcut from "../wiki_blocks/shortcut";
import Spacer from "../wiki_blocks/spacer";

// import tunes
import SpacingTune from "../wiki_blocks/spacing_tune";

frappe.provide("frappe.wiki_block");

frappe.wiki_block.blocks = {
	header: Header,
	paragraph: Paragraph,
	card: Card,
	chart: Chart,
	shortcut: Shortcut,
	spacer: Spacer,
};

frappe.wiki_block.tunes = {
	spacing_tune: SpacingTune
};