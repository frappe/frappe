// PAGE

var pages=[];
var stylesheets = [];

function Page(page_name, content) {	
	var me = this;
	this.name = page_name;

	this.onshow = function() {
		// default set_title
		set_title(me.doc.page_title ? me.doc.page_title : me.name);
		
		// onshow
		try {
			if(pscript['onshow_'+me.name]) pscript['onshow_'+me.name](); // onload
		} catch(e) { submit_error(e); }
		
		// clear cur_frm
		cur_frm = null;
	}

	this.wrapper = page_body.add_page(page_name, this.onshow);
	this.cont = this.wrapper // bc

	if(content)
		this.wrapper.innerHTML = content;

	if(page_name == home_page)
		pages['_home'] = this;
	
	return this;
}


function render_page(page_name, menuitem) {
	if(!page_name)return;
	if((!locals['Page']) || (!locals['Page'][page_name])) {
		// no page, go home
		loadpage('_home');
		return;
	}
	var pdoc = locals['Page'][page_name];


	// style
	if(pdoc.style) set_style(pdoc.style)

	// stylesheet
	if(pdoc.stylesheet) { set_style(locals.Stylesheet[pdoc.stylesheet].stylesheet); stylesheets.push(pdoc.stylesheet); }

	// create page
	var p = new Page(page_name, pdoc._Page__content?pdoc._Page__content:pdoc.content);
	// script
	var script = pdoc.__script ? pdoc.__script : pdoc.script;
	p.doc = pdoc;

	if(script) {
		try { eval(script); } catch(e) { submit_error(e); }
	}

	// change
	page_body.change_to(page_name);	
	
	// run onload
	try {
		if(pscript['onload_'+page_name]) pscript['onload_'+page_name](); // onload
	} catch(e) { submit_error(e); }
		
	//setTimeout('page_body.pages[cur_page].set_page_height()', 100);
	return p;
}

function refresh_page(page_name) {
	var fn = function(r, rt) {
		render_page(page_name)	
	}
	$c('webnotes.widgets.page.getpage', {'name':page_name, stylesheets:JSON.stringify(stylesheets)}, fn);
}
