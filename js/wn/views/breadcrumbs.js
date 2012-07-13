wn.provide('wn.views');
wn.views.breadcrumbs = function(appframe, module, doctype, name) {
	appframe.clear_breadcrumbs();

	if(name) {
		appframe.add_breadcrumb(name);
	} else if(doctype) {
		appframe.add_breadcrumb(doctype + ' List');
	} else if(module) {
		appframe.add_breadcrumb(module);
	}

	if(name && doctype && (!locals['DocType'][doctype].issingle)) {
		appframe.add_breadcrumb(repl(' in <a href="#!List/%(doctype)s">%(doctype)s List</a>',
			{doctype: doctype}))
	};
	
	if(doctype && module && wn.modules && wn.modules[module]) {
		appframe.add_breadcrumb(repl(' in <a href="#!%(module_page)s">%(module)s</a>',
			{module: module, module_page: wn.modules[module] }))
	}
}