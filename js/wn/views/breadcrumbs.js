wn.provide('wn.views');
wn.views.breadcrumbs = function(parent, module, doctype, name) {
	$(parent).empty();
	var $bspan = $(parent);

	if(name) {
		$bspan.append('<span class="appframe-title">' + name + '</span>');
	} else if(doctype) {
		$bspan.append('<span class="appframe-title">' + doctype + ' List </span>');
	} else if(module) {
		$bspan.append('<span class="appframe-title">' + module + '</span>');		
	}

	if(name && doctype && (!locals['DocType'][doctype].issingle)) {
		$bspan.append(repl('<span> in <a href="#!List/%(doctype)s">%(doctype)s List</a></span>',
			{doctype: doctype}))
	};
	
	if(doctype && module && wn.modules && wn.modules[module]) {
		$bspan.append(repl('<span> in <a href="#!%(module_page)s">%(module)s</a></span>',
			{module: module, module_page: wn.modules[module] }))
	}
	//$bspan.appendTo(parent);
}