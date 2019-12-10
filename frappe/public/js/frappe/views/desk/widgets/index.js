import ModuleWidget from './module_widget.js'
import LinkWidget from './link_widget.js'


const widget_factory = {
	'module': ModuleWidget,
	'link': LinkWidget
}

export function get_widget_class(widget_type) {
	return widget_factory[widget_type];
};
