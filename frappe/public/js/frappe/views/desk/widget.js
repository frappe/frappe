import ModuleWidget from './module_widget.js'


const widget_factory = {
	'module': ModuleWidget,
	'link': ModuleWidget
}

export function get_widget_class(widget_type) {
	return widget_factory[widget_type];
};
