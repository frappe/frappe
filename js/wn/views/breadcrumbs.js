wn.provide('wn.views');
wn.views.breadcrumbs = function(parent, module, doctype, name) {
	$(parent).empty();
	var $bspan = $(repl('<span class="breadcrumbs">\
		<a href="#%(home_page)s">Home</a></span>', {home_page: wn.boot.home_page}));
	if(module) {
		$bspan.append(repl(' / <a href="#!%(module_page)s">%(module)s Home</a>',
			{module: module, module_page: erpnext.modules[module] }))
	}
	if(doctype && (locals.DocType[doctype] && !locals.DocType[doctype].issingle)) {
		$bspan.append(repl(' / <a href="#!List/%(doctype)s">%(doctype)s</a>',
			{doctype: doctype}))
	}
	if(name) {
		$bspan.append(' / ' + name.bold())
	}
	$bspan.appendTo(parent);
}
