import ModuleWidget from "./module_widget.js";
import LinkWidget from "./link_widget.js";
import ModuleItemsWidget from "./module_items_widget.js";
import BaseWidget from "./base_widget.js";

const widget_factory = {
	module: ModuleWidget,
	link: LinkWidget,
	module_details: ModuleItemsWidget
};

export function get_widget_class(widget_type) {
	return widget_factory[widget_type];
}
