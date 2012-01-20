// ABOUT

wn.provide('wn.ui.misc');
wn.ui.misc.about = function() {
	if(!wn.ui.misc.about_dialog) {
		var d = new wn.widgets.Dialog({title:'About wnframework'})
	
		$(d.body).html(repl("<div style='padding: 20px'<p><b>Application Name:</b> %(name)s</p>\
		<p><b>Version:</b> %(version)s</p>\
		<p><b>License:</b> %(license)s</p>\
		<p><b>Source Code:</b> %(source)s</p>\
		<p><b>Publisher:</b> %(publisher)s</p>\
		<p><b>Copyright:</b> %(copyright)s</p></div>", wn.app));
	
		wn.ui.misc.about_dialog = d;		
	}

	wn.ui.misc.about_dialog.show();
}
