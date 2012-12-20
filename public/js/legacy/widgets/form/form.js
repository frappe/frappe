// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
// 

/* Form page structure

	+ this.parent (either FormContainer or Dialog)
 		+ this.wrapper
 			+ this.content
				+ wn.PageLayout	(this.page_layout)
				+ this.wrapper
					+ this.wtab (table)
						+ this.main
							+ this.head
							+ this.body
								+ this.layout
								+ this.footer
						+ this.sidebar
				+ this.print_wrapper
					+ this.head
*/

wn.provide('_f');
wn.provide('wn.ui.form');

wn.ui.form.Controller = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
	}
});

_f.frms = {};

_f.Frm = function(doctype, parent, in_form) {
	this.docname = '';
	this.doctype = doctype;
	this.display = 0;
	this.refresh_if_stale_for = 600;
		
	var me = this;
	this.is_editable = {};
	this.opendocs = {};
	this.sections = [];
	this.grids = [];
	this.cscript = new wn.ui.form.Controller({frm:this});
	this.pformat = {};
	this.fetch_dict = {};
	this.parent = parent;
	this.tinymce_id_list = [];
	
	this.setup_meta(doctype);
	
	// show in form instead of in dialog, when called using url (router.js)
	this.in_form = in_form ? true : false;
	
	// notify on rename
	var me = this;
	$(document).bind('rename', function(event, dt, old_name, new_name) {
		if(dt==me.doctype)
			me.rename_notify(dt, old_name, new_name)
	});
}

// ======================================================================================

_f.Frm.prototype.check_doctype_conflict = function(docname) {
	var me = this;
	if(this.doctype=='DocType' && docname=='DocType') {
		msgprint('Allowing DocType, DocType. Be careful!')
	} else if(this.doctype=='DocType') {
		if (wn.views.formview[docname] || wn.pages['List/'+docname]) {
			msgprint("Cannot open DocType when its instance is open")
			throw 'doctype open conflict'
		}
	} else {
		if (wn.views.formview.DocType && wn.views.formview.DocType.frm.opendocs[this.doctype]) {
			msgprint("Cannot open instance when its DocType is open")
			throw 'doctype open conflict'
		}		
	}
}

_f.Frm.prototype.setup = function() {

	var me = this;
	this.fields = [];
	this.fields_dict = {};

	// wrapper
	this.wrapper = this.parent;
	
	// create area for print fomrat
	this.setup_print_layout();
	
	// 2 column layout
	this.setup_std_layout();

	// client script must be called after "setup" - there are no fields_dict attached to the frm otherwise
	this.setup_client_script();
	
	this.setup_done = true;
}

// ======================================================================================

_f.Frm.prototype.setup_print_layout = function() {
	var me = this;
	this.print_wrapper = $a(this.wrapper, 'div');
	wn.ui.make_app_page({
		parent: this.print_wrapper,
		single_column: true,
		set_document_title: false,
		title: me.doctype + ": Print View",
		module: me.meta.module
	});
	
	var appframe = this.print_wrapper.appframe;
	appframe.add_button("View Details", function() {
		me.edit_doc();
	}).addClass("btn-success");
	
	appframe.add_button("Print", function() {
		me.print_doc();
	}, 'icon-print');

	this.$print_view_select = appframe.add_select("Select Preview", this.print_formats)
		.css({"float":"right"})
		.val(this.print_formats[0])
		.change(function() {
			me.refresh_print_layout();
		})
	
	appframe.add_ripped_paper_effect(this.print_wrapper);
	
	var layout_main = $(this.print_wrapper).find(".layout-main");
	this.print_body = $("<div style='margin: 25px'>").appendTo(layout_main)
		.css("min-height", "400px").get(0);
		
}


_f.Frm.prototype.onhide = function() { if(_f.cur_grid_cell) _f.cur_grid_cell.grid.cell_deselect(); }

// ======================================================================================

_f.Frm.prototype.setup_std_layout = function() {
	this.page_layout = new wn.PageLayout({
		parent: this.wrapper,
		main_width: (this.meta.in_dialog && !this.in_form) ? '100%' : '75%',
		sidebar_width: (this.meta.in_dialog && !this.in_form) ? '0%' : '25%'
	})	

	// only tray
	this.meta.section_style='Simple'; // always simple!
	
	// layout
	this.layout = new Layout(this.page_layout.body, '100%');
	
	// sidebar
	if(this.meta.in_dialog && !this.in_form) {
		// hide sidebar
		$(this.page_layout.wrapper).removeClass('layout-wrapper-background');
		$(this.page_layout.main).removeClass('layout-main-section');
		$(this.page_layout.sidebar_area).toggle(false);
	} else {
		// module link
		this.setup_sidebar();
	}
	
	// watermark
	$('<div style="font-size: 21px; color: #aaa; float: right;\
		margin-top: -5px; margin-right: -5px; z-index: 5;">' 
		+ this.doctype + '</div>')
		.prependTo(this.page_layout.main);
	
	// footer
	this.setup_footer();
		
	// header - no headers for tables and guests
	if(!(this.meta.istable || (this.meta.in_dialog && !this.in_form))) 
		this.frm_head = new _f.FrmHeader(this.page_layout.head, this);
			
	// create fields
	this.setup_fields_std();
	
}

_f.Frm.prototype.setup_print = function() { 
	this.print_formats = wn.meta.get_print_formats(this.meta.name);
	this.print_sel = $a(null, 'select', '', {width:'160px'});
	add_sel_options(this.print_sel, this.print_formats);
	this.print_sel.value = this.print_formats[0];
}

_f.Frm.prototype.print_doc = function() {
	if(this.doc.docstatus==2)  {
		msgprint("Cannot Print Cancelled Documents.");
		return;
	}

	_p.show_dialog(); // multiple options
}

// email the form
_f.Frm.prototype.email_doc = function(message) {
	new wn.views.CommunicationComposer({
		doc: this.doc,
		subject: wn._(this.meta.name) + ': ' + this.docname,
		recipients: this.doc.email || this.doc.email_id || this.doc.contact_email,
		attach_document_print: true,
		message: message,
		real_name: this.doc.real_name || this.doc.contact_display || this.doc.contact_name
	});
}

// email the form
_f.Frm.prototype.rename_doc = function() {
	wn.model.rename_doc(this.doctype, this.docname);
}

// notify this form of renamed records
_f.Frm.prototype.rename_notify = function(dt, old, name) {	
	// from form
	if(this.meta.istable) 
		return;
	
	if(this.docname == old)
		this.docname = name;
	else
		return;

	// editable
	this.is_editable[name] = this.is_editable[old];
	delete this.is_editable[old];

	// cleanup
	if(this && this.opendocs[old]) {
		// delete docfield copy
		wn.meta.docfield_copy[dt][name] = wn.meta.docfield_copy[dt][old];
		delete wn.meta.docfield_copy[dt][old];
	}

	delete this.opendocs[old];
	this.opendocs[name] = true;
	
	if(this.meta.in_dialog || !this.in_form) {
		return;
	}
	
	wn.re_route[window.location.hash] = '#Form/' + encodeURIComponent(this.doctype) + '/' + encodeURIComponent(name);
	wn.set_route('Form', this.doctype, name);
}

// SETUP

_f.Frm.prototype.setup_meta = function(doctype) {
	this.meta = wn.model.get_doc('DocType',this.doctype);
	this.perm = wn.perm.get_perm(this.doctype); // for create
	if(this.meta.istable) { this.meta.in_dialog = 1 }
	this.setup_print();
}

_f.Frm.prototype.setup_sidebar = function() {
	this.sidebar = new wn.widgets.form.sidebar.Sidebar(this);
}

_f.Frm.prototype.setup_footer = function() {
	var me = this;
	
	// footer toolbar
	var f = this.page_layout.footer;

	// save buttom
	f.save_area = $a(this.page_layout.footer,'div','',{display:'none', marginTop:'11px'});
	f.help_area = $a(this.page_layout.footer,'div');

	var b = $("<button class='btn btn-info'><i class='icon-save'></i> Save</button>")
		.click(function() { me.save("Save", null, me); }).appendTo(f.save_area);
	
	// show / hide save
	f.show_save = function() {
		$ds(me.page_layout.footer.save_area);
	}

	f.hide_save = function() {
		$dh(me.page_layout.footer.save_area);
	}
}

_f.Frm.prototype.set_intro = function(txt) {
	if(!this.intro_area) {
		this.intro_area = $('<div class="alert form-intro-area" style="margin-top: 20px;">')
			.insertBefore(this.page_layout.body.firstChild);
	}
	if(txt) {
		if(txt.search(/<p>/)==-1) txt = '<p>' + txt + '</p>';
		this.intro_area.html(txt);
	} else {
		this.intro_area.remove();
		this.intro_area = null;
	}
}

_f.Frm.prototype.set_footnote = function(txt) {
	if(!this.footnote_area) {
		this.footnote_area = $('<div class="alert form-intro-area">')
			.insertAfter(this.page_layout.body.lastChild);
	}
	if(txt) {
		if(txt.search(/<p>/)==-1) txt = '<p>' + txt + '</p>';
		this.footnote_area.html(txt);
	} else {
		this.footnote_area.remove();
		this.footnote_area = null;
	}
}


_f.Frm.prototype.setup_fields_std = function() {
	var fl = wn.meta.docfield_list[this.doctype]; 

	fl.sort(function(a,b) { return a.idx - b.idx});

	if(fl[0]&&fl[0].fieldtype!="Section Break" || get_url_arg('embed')) {
		this.layout.addrow(); // default section break
		if(fl[0].fieldtype!="Column Break") {// without column too
			var c = this.layout.addcell();
			$y(c.wrapper, {padding: '8px'});			
		}
	}

	var sec;
	for(var i=0;i<fl.length;i++) {
		var f=fl[i];
				
		// if section break and next item 
		// is a section break then ignore
		if(f.fieldtype=='Section Break' && fl[i+1] && fl[i+1].fieldtype=='Section Break') 
			continue;
		
		var fn = f.fieldname?f.fieldname:f.label;
				
		var fld = make_field(f, this.doctype, this.layout.cur_cell, this);

		this.fields[this.fields.length] = fld;
		this.fields_dict[fn] = fld;

		if(sec && ['Section Break', 'Column Break'].indexOf(f.fieldtype)==-1) {
			fld.parent_section = sec;
			sec.fields.push(fld);			
		}
		
		if(f.fieldtype=='Section Break') {
			sec = fld;
			this.sections.push(fld);
		}
		
		// default col-break after sec-break
		if((f.fieldtype=='Section Break')&&(fl[i+1])&&(fl[i+1].fieldtype!='Column Break')) {
			var c = this.layout.addcell();
			$y(c.wrapper, {padding: '8px'});			
		}
	}
}

_f.Frm.prototype.add_custom_button = function(label, fn, icon) {
	this.frm_head.appframe.add_button(label, fn, icon);
}
_f.Frm.prototype.clear_custom_buttons = function() {
	this.frm_head.refresh_toolbar()
}

_f.Frm.prototype.add_fetch = function(link_field, src_field, tar_field) {
	if(!this.fetch_dict[link_field]) {
		this.fetch_dict[link_field] = {'columns':[], 'fields':[]}
	}
	this.fetch_dict[link_field].columns.push(src_field);
	this.fetch_dict[link_field].fields.push(tar_field);
}

_f.Frm.prototype.setup_client_script = function() {
	// setup client obj

	if(this.meta.client_script_core || this.meta.client_script || this.meta.__js) {
		this.runclientscript('setup', this.doctype, this.docname);
	}
}

_f.Frm.prototype.refresh_print_layout = function() {
	$ds(this.print_wrapper);
	$dh(this.page_layout.wrapper);

	var me = this;
	var print_callback = function(print_html) {
		me.print_body.innerHTML = print_html;
	}
	
	// print head
	if(cur_frm.doc.select_print_heading)
		cur_frm.set_print_heading(cur_frm.doc.select_print_heading)
	
	if(user!='Guest') {
		$di(this.view_btn_wrapper);

		// archive
		if(cur_frm.doc.__archived) {
			$dh(this.view_btn_wrapper);
		}
	} else {
		$dh(this.view_btn_wrapper);		
		$dh(this.print_close_btn);		
	}

	// create print format here
	_p.build(this.$print_view_select.val(), print_callback, null, 1);
}


_f.Frm.prototype.show_the_frm = function() {
	// show the dialog
	if(this.meta.in_dialog && !this.parent.dialog.display) {
		if(!this.meta.istable)
			this.parent.table_form = false;
		this.parent.dialog.show();
	}	
}

_f.Frm.prototype.set_print_heading = function(txt) {
	this.pformat[cur_frm.docname] = txt;
}

_f.Frm.prototype.defocus_rest = function() {
	// deselect others
	if(_f.cur_grid_cell) _f.cur_grid_cell.grid.cell_deselect();
}

_f.Frm.prototype.refresh_header = function() {
	// set title
	// main title
	if(!this.meta.in_dialog || this.in_form) {
		set_title(this.meta.issingle ? this.doctype : this.docname);
	}	
	
	// form title
	//this.page_layout.main_head.innerHTML = '<h2>'+this.docname+'</h2>';

	// show / hide buttons
	if(this.frm_head)this.frm_head.refresh();
	
	// add to recent
	if(wn.ui.toolbar.recent) 
		wn.ui.toolbar.recent.add(this.doctype, this.docname, 1);	
}

_f.Frm.prototype.check_doc_perm = function() {
	// get perm
	var dt = this.parent_doctype?this.parent_doctype : this.doctype;
	var dn = this.parent_docname?this.parent_docname : this.docname;
	this.perm = wn.perm.get_perm(dt, dn);
	this.orig_perm = wn.perm.get_perm(dt, dn, 1);
				  
	if(!this.perm[0][READ]) { 
		if(user=='Guest') {
			// allow temp access? via encryted akey
			if(_f.temp_access[dt] && _f.temp_access[dt][dn]) {
				this.perm = [[1,0,0]]
				return 1;
			}
		}
		window.history.back();
		return 0;
	}
	return 1
}

_f.Frm.prototype.refresh = function(docname) {
	// record switch
	if(docname) {
		if(this.docname != docname && (!this.meta.in_dialog || this.in_form) && 
			!this.meta.istable) 
			scroll(0, 0);
		this.docname = docname;
	}
	if(!this.meta.istable) {
		cur_frm = this;
		this.parent.cur_frm = this;
	}
	
	if(this.docname) { // document to show

		// check permissions
		if(!this.check_doc_perm()) return;

		// set the doc
		this.doc = wn.model.get_doc(this.doctype, this.docname);	  
		
		// check if doctype is already open
		if (!this.opendocs[this.docname]) {
			this.check_doctype_conflict(this.docname);
		} else {
			if(this.doc && this.doc.__last_sync_on && 
				(new Date() - this.doc.__last_sync_on) / 1000 > this.refresh_if_stale_for) {
				this.reload_doc();
				return;
			}
		}

		// do setup
		if(!this.setup_done) this.setup();

		// set customized permissions for this record
		this.runclientscript('set_perm',this.doctype, this.docname);
		
		// load the record for the first time, if not loaded (call 'onload')
		cur_frm.cscript.is_onload = false;
		if(!this.opendocs[this.docname]) { 
			cur_frm.cscript.is_onload = true;
			this.setnewdoc(this.docname); 
		}

		// editable
		if(this.doc.__islocal) 
			this.is_editable[this.docname] = 1; // new is editable

		this.editable = this.is_editable[this.docname];
		
		if(this.editable || (!this.editable && this.meta.istable)) {
			// show form layout (with fields etc)
			// ----------------------------------
			if(this.print_wrapper) {
				$dh(this.print_wrapper);
				$ds(this.page_layout.wrapper);
			}

			// header
			if(!this.meta.istable) { 
				this.refresh_header();
				this.sidebar && this.sidebar.refresh();
			}

			// call trigger
	 		this.runclientscript('refresh');
			
			// trigger global trigger
			// to use this
			$(document).trigger('form_refresh');
						
			// fields
			this.refresh_fields();
			
			// dependent fields
			this.refresh_dependency();

			// footer
			this.refresh_footer();
			
			// layout
			if(this.layout) this.layout.show();

			// call onload post render for callbacks to be fired
			if(cur_frm.cscript.is_onload) {
				this.runclientscript('onload_post_render', this.doctype, this.docname);
			}
				
			// focus on first input
			
			if(this.doc.docstatus==0) {
				$(this.wrapper).find('.form-layout-row :input:first').focus();
			}
		
		} else {
			// show print layout
			// ----------------------------------
			this.refresh_header();
			if(this.print_wrapper) {
				this.refresh_print_layout();
			}
			this.runclientscript('edit_status_changed');
		}

		$(cur_frm.wrapper).trigger('render_complete');
	} 
}

_f.Frm.prototype.refresh_footer = function() {
	var f = this.page_layout.footer;
	if(f.save_area) {
		if(this.editable && (!this.meta.in_dialog || this.in_form) 
			&& this.doc.docstatus==0 && !this.meta.istable && this.perm[0][WRITE]
			&& (this.fields && this.fields.length > 7) && !this.save_disabled) {
			f.show_save();
		} else {
			f.hide_save();
		}
	}
}

_f.Frm.prototype.refresh_field = function(fname) {
	cur_frm.fields_dict[fname] && cur_frm.fields_dict[fname].refresh
		&& cur_frm.fields_dict[fname].refresh();
}

_f.Frm.prototype.refresh_fields = function() {
	// refresh fields
	for(var i=0; i<this.fields.length; i++) {
		var f = this.fields[i];
		f.perm = this.perm;
		f.docname = this.docname;
		
		// if field is identifiable (not blank section or column break)
		// get the "customizable" parameters for this record
		var fn = f.df.fieldname || f.df.label;
		if(fn)
			f.df = wn.meta.get_docfield(this.doctype, fn, this.docname);
			
		if(f.df.fieldtype!='Section Break' && f.refresh) {
			f.refresh();
		}
	}

	// refresh sections
	$.each(this.sections, function(i, f) {
		f.refresh(true);
	})

	// cleanup activities after refresh
	this.cleanup_refresh(this);
}


_f.Frm.prototype.cleanup_refresh = function() {
	var me = this;
	if(me.fields_dict['amended_from']) {
		if (me.doc.amended_from) {
			unhide_field('amended_from');
			if (me.fields_dict['amendment_date']) unhide_field('amendment_date');
		} else {
			hide_field('amended_from'); 
			if (me.fields_dict['amendment_date']) hide_field('amendment_date');
		}
	}

	if(me.fields_dict['trash_reason']) {
		if(me.doc.trash_reason && me.doc.docstatus == 2) {
			unhide_field('trash_reason');
		} else {
			hide_field('trash_reason');
		}
	}

	if(me.meta.autoname && me.meta.autoname.substr(0,6)=='field:' && !me.doc.__islocal) {
		var fn = me.meta.autoname.substr(6);
		cur_frm.toggle_display(fn, false);
	}
}

// Resolve "depends_on" and show / hide accordingly

_f.Frm.prototype.refresh_dependency = function() {
	var me = this;
	var doc = locals[this.doctype][this.docname];

	// build dependants' dictionary	
	var has_dep = false;
	
	for(fkey in me.fields) { 
		var f = me.fields[fkey];
		f.dependencies_clear = true;
		if(f.df.depends_on) {
			has_dep = true;
		}
	}
	
	if(!has_dep)return;


	// show / hide based on values
	for(var i=me.fields.length-1;i>=0;i--) { 
		var f = me.fields[i];
		f.guardian_has_value = true;
		if(f.df.depends_on) {
			// evaluate guardian
			var v = doc[f.df.depends_on];
			if(f.df.depends_on.substr(0,5)=='eval:') {
				f.guardian_has_value = eval(f.df.depends_on.substr(5));
			} else if(f.df.depends_on.substr(0,3)=='fn:') {
				f.guardian_has_value = me.runclientscript(f.df.depends_on.substr(3), me.doctype, me.docname);
			} else {
				if(!v) {
					f.guardian_has_value = false;
				}
			}

			// show / hide
			if(f.guardian_has_value) {
				f.df.hidden = 0;
				f.refresh();
			} else {
				f.df.hidden = 1;
				f.refresh();
			}
		}
	}
}

// setnewdoc is called when a record is loaded for the first time
// ======================================================================================

_f.Frm.prototype.setnewdoc = function(docname) {
	// moved this call to refresh function
	// this.check_doctype_conflict(docname);

	// if loaded
	if(this.opendocs[docname]) { // already exists
		this.docname=docname;
		return;
	}

	// make a copy of the doctype for client script settings
	// each record will have its own client script
	wn.meta.make_docfield_copy_for(this.doctype,docname);

	this.docname = docname;

	var me = this;
	var viewname = this.meta.issingle ? this.doctype : docname;

	// Client Script
	this.runclientscript('onload', this.doctype, this.docname);
	
	this.is_editable[docname] = 1;
	if(cint(this.meta.read_only_onload)) this.is_editable[docname] = 0;
		
	this.opendocs[docname] = true;
}

_f.Frm.prototype.edit_doc = function() {
	// set fields
	this.is_editable[this.docname] = true;
	this.refresh();
}


_f.Frm.prototype.show_doc = function(dn) {
	this.refresh(dn);
}


_f.Frm.prototype.runscript = function(scriptname, callingfield, onrefresh) {
	var me = this;
	if(this.docname) {
		// make doc list
		var doclist = wn.model.compress(make_doclist(this.doctype, this.docname));
		// send to run
		if(callingfield)
			$(callingfield.input).set_working();

		$c('runserverobj', {'docs':doclist, 'method':scriptname }, 
			function(r, rtxt) { 
				// run refresh
				if(onrefresh)
					onrefresh(r,rtxt);

				// fields
				me.refresh_fields();
				
				// dependent fields
				me.refresh_dependency();

				// enable button
				if(callingfield)
					$(callingfield.input).done_working();
			}
		);
	}
}

_f.Frm.prototype.runclientscript = function(caller, cdt, cdn) {
	if(!cdt)cdt = this.doctype;
	if(!cdn)cdn = this.docname;

	var ret = null;
	var doc = locals[cur_frm.doc.doctype][cur_frm.doc.name];
	try {
		if(this.cscript[caller])
			ret = this.cscript[caller](doc, cdt, cdn);

		if(this.cscript['custom_'+caller])
			ret += this.cscript['custom_'+caller](doc, cdt, cdn);
			
	} catch(e) {
		validated = false;
		console.log(e);
	}

	if(caller && caller.toLowerCase()=='setup') {

		var doctype = wn.model.get_doc('DocType', this.doctype);
		
		// js
		var cs = doctype.__js || (doctype.client_script_core + doctype.client_script);
		if(cs) {
			try {
				var tmp = eval(cs);
			} catch(e) {
				console.log(e);
			}
		}

		// css
		if(doctype.__css) set_style(doctype.__css)
		
		// ---Client String----
		if(doctype.client_string) { // split client string
			this.cstring = {};
			var elist = doctype.client_string.split('---');
			for(var i=1;i<elist.length;i=i+2) {
				this.cstring[strip(elist[i])] = elist[i+1];
			}
		}
	}
	return ret;
}

_f.Frm.prototype.copy_doc = function(onload, from_amend) {
	if(!this.perm[0][CREATE]) {
		msgprint('You are not allowed to create '+this.meta.name);
		return;
	}
	
	var dn = this.docname;
	// copy parent
	var newdoc = wn.model.copy_doc(this.doctype, dn, from_amend);

	// do not copy attachments
	if(this.meta.allow_attach && newdoc.file_list && !from_amend)
		newdoc.file_list = null;
	
	// copy chidren
	var dl = make_doclist(this.doctype, dn);

	// table fields dict - for no_copy check
	var tf_dict = {};

	for(var d in dl) {
		d1 = dl[d];
		
		// get tabel field
		if(d1.parentfield && !tf_dict[d1.parentfield]) {
			tf_dict[d1.parentfield] = wn.meta.get_docfield(d1.parenttype, d1.parentfield);
		}
		
		if(d1.parent==dn && cint(tf_dict[d1.parentfield].no_copy)!=1) {
			var ch = wn.model.copy_doc(d1.doctype, d1.name, from_amend);
			ch.parent = newdoc.name;
			ch.docstatus = 0;
			ch.owner = user;
			ch.creation = '';
			ch.modified_by = user;
			ch.modified = '';
		}
	}

	newdoc.__islocal = 1;
	newdoc.docstatus = 0;
	newdoc.owner = user;
	newdoc.creation = '';
	newdoc.modified_by = user;
	newdoc.modified = '';

	if(onload)onload(newdoc);

	loaddoc(newdoc.doctype, newdoc.name);
}

_f.Frm.prototype.reload_doc = function() {
	this.check_doctype_conflict(this.docname);

	var me = this;
	var onsave = function(r, rtxt) {
		// n tweets and last comment				
		me.runclientscript('setup', me.doctype, me.docname);
		me.refresh();
	}

	if(me.doc.__islocal) { 
		// reload only doctype
		$c('webnotes.widgets.form.load.getdoctype', {'doctype':me.doctype }, onsave, null, null, 'Refreshing ' + me.doctype + '...');
	} else {
		// reload doc and docytpe
		$c('webnotes.widgets.form.load.getdoc', {'name':me.docname, 'doctype':me.doctype, 'getdoctype':1, 'user':user}, onsave, null, null, 'Refreshing ' + me.docname + '...');
	}
}

var validated;
_f.Frm.prototype.save = function(save_action, callback, btn) {
	$(document.activeElement).blur();
	var me = this;
	var doclist = new wn.model.DocList(this.doctype, this.docname);
	
	// validate
	if(save_action!="Cancel") {
		validated = true;
		this.runclientscript('validate');
		if(!validated) {
			return;
		}
	}
	doclist.save(save_action || "Save", function(r) {
		if(!r.exc) {
			me.refresh();
		}
		callback && callback(r);
	}, btn);
}


_f.Frm.prototype.savesubmit = function(btn) {
	var me = this;
	wn.confirm("Permanently Submit "+this.docname+"?", function() {
		me.save('Submit', function(r) {
			if(!r.exc) {
				me.runclientscript('on_submit', me.doctype, me.docname);
			}
		}, btn);
	});
}

_f.Frm.prototype.savecancel = function(btn) {
	var me = this;
	wn.confirm("Permanently Cancel "+this.docname+"?", function() {
		var doclist = new wn.model.DocList(me.doctype, me.docname);
		doclist.cancel(function(r) {
			if(!r.exc) me.refresh();
		}, btn);
	});
}

// delete the record
_f.Frm.prototype.savetrash = function() {
	wn.model.delete_doc(this.doctype, this.docname, function(r) {
		window.history.back();
	})
}

_f.Frm.prototype.amend_doc = function() {
	if(!this.fields_dict['amended_from']) {
		alert('"amended_from" field must be present to do an amendment.');
		return;
	}
	var me = this;
    var fn = function(newdoc) {
      newdoc.amended_from = me.docname;
      if(me.fields_dict && me.fields_dict['amendment_date'])
	      newdoc.amendment_date = dateutil.obj_to_str(new Date());
    }
    this.copy_doc(fn, 1);
}

_f.Frm.prototype.disable_save = function() {
	// IMPORTANT: this function should be called in refresh event
	cur_frm.save_disabled = true;
	cur_frm.page_layout.footer.hide_save();
	cur_frm.frm_head.appframe.buttons.Save.toggle(false);
}

_f.get_value = function(dt, dn, fn) {
	if(locals[dt] && locals[dt][dn]) 
		return locals[dt][dn][fn];
}

_f.Frm.prototype.set_value_in_locals = function(dt, dn, fn, v) {
	var d = locals[dt][dn];

	if (!d) return;
	
	var changed = d[fn] != v;
	if(changed && (d[fn]==null || v==null) && (cstr(d[fn])==cstr(v))) 
		changed = false;

	if(changed) {
		d[fn] = v;
		if(d.parenttype)
			d.__unsaved = 1;
		this.set_unsaved();
	}
}

_f.Frm.prototype.set_unsaved = function() {
	if(cur_frm.doc.__unsaved) return;
	cur_frm.doc.__unsaved = 1;
	
	var frm_head;
	if(cur_frm.frm_head) {
		frm_head = cur_frm.frm_head;
	} else if(wn.container.page.frm && wn.container.page.frm.frm_head) {
		frm_head = wn.container.page.frm.frm_head
	}
	
	if(frm_head) frm_head.refresh_labels();
	
}

_f.Frm.prototype.show_comments = function() {
	if(!cur_frm.comments) {
		cur_frm.comments = new Dialog(540, 400, 'Comments');
		cur_frm.comments.comment_body = $a(cur_frm.comments.body, 'div', 'dialog_frm');
		$y(cur_frm.comments.body, {backgroundColor:'#EEE'});
		cur_frm.comments.list = new CommentList(cur_frm.comments.comment_body);
	}
	cur_frm.comments.list.dt = cur_frm.doctype;
	cur_frm.comments.list.dn = cur_frm.docname;
	cur_frm.comments.show();
	cur_frm.comments.list.run();
}