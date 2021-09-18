// import blocks
import Header from "./header";
import Paragraph from "./paragraph";
import Card from "./card";
import Chart from "./chart";
import Shortcut from "./shortcut";
import Spacer from "./spacer";
import Onboarding from "./onboarding";

// import tunes
import SpacingTune from "./spacing_tune";

frappe.provide("frappe.wspace_block");

frappe.wspace_block.blocks = {
	header: Header,
	paragraph: Paragraph,
	card: Card,
	chart: Chart,
	shortcut: Shortcut,
	spacer: Spacer,
	onboarding: Onboarding,
};

frappe.wspace_block.tunes = {
	spacing_tune: SpacingTune
};