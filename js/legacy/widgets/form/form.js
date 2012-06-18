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
	 			+ this.saved_wrapper
				+ wn.PageLayout	(this.page_layout_layout)
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

_f.frms = {};

_f.Frm = function(doctype, parent) {
	this.docname = '';
	this.doctype = doctype;
	this.display = 0;
		
	var me = this;
	this.is_editable = {};
	this.opendocs = {};
	this.sections = [];
	this.grids = [];
	this.cscript = {};
	this.pformat = {};
	this.fetch_dict = {};
	this.parent = parent;
	this.tinymce_id_list = [];
	
	this.setup_meta(doctype);
	
	// notify on rename
	var me = this;
	$(document).bind('rename', function(event, dt, old_name, new_name) {
		//console.log(arguments)
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
		if(wn.views.formview[docname]) {
			msgprint("Cannot open DocType when its instance is open")
			throw 'doctype open conflict'
		}
	} else {
		if(wn.views.formview.DocType && wn.views.formview.DocType.frm.opendocs[this.doctype]) {
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

	// thank you goes here (in case of Guest, don't refresh, just say thank you!)
	this.saved_wrapper = $a(this.wrapper, 'div');
	
	// 2 column layout
	this.setup_std_layout();

	// client script must be called after "setup" - there are no fields_dict attached to the frm otherwise
	this.setup_client_script();
	
	this.setup_done = true;
}

// ======================================================================================

_f.Frm.prototype.setup_print_layout = function() {
	this.print_wrapper = $a(this.wrapper, 'div');
	this.print_head = $a(this.print_wrapper, 'div');
	this.print_body = $a(this.print_wrapper,'div', 'layout_wrapper', {
		padding:'23px',
		minHeight: '800px'
	});
	
	var t= make_table(this.print_head, 1 ,2, '100%', [], {padding: '6px'});
	this.view_btn_wrapper = $a($td(t,0,0) , 'span', 'green_buttons');
	this.view_btn = $btn(this.view_btn_wrapper, 'View Details', function() { cur_frm.edit_doc() }, 
		{marginRight:'4px'}, 'green');

	this.print_btn = $btn($td(t,0,0), 'Print', function() { cur_frm.print_doc() });

	$y($td(t,0,1), {textAlign: 'right'});
	this.print_close_btn = $btn($td(t,0,1), 'Close', function() { window.history.back(); });
}


_f.Frm.prototype.onhide = function() { if(_f.cur_grid_cell) _f.cur_grid_cell.grid.cell_deselect(); }

// ======================================================================================

_f.Frm.prototype.setup_std_layout = function() {
	this.page_layout = new wn.PageLayout({
		parent: this.wrapper,
		main_width: this.meta.in_dialog ? '100%' : '75%',
		sidebar_width: this.meta.in_dialog ? '0%' : '25%'
	})	
			
	// only tray
	this.meta.section_style='Simple'; // always simple!
	
	// layout
	this.layout = new Layout(this.page_layout.body, '100%');
	
	// sidebar
	if(this.meta.in_dialog) {
		// hide sidebar
		$(this.page_layout.wrapper).removeClass('layout-wrapper-background');
		$(this.page_layout.main).removeClass('layout-main-section');
		$(this.page_layout.sidebar_area).toggle(false);
	} else {
		// module link
		this.setup_sidebar();
	}
		
	// footer
	this.setup_footer();		
	
		
	// header - no headers for tables and guests
	if(!(this.meta.istable || user=='Guest' || this.meta.in_dialog)) 
		this.frm_head = new _f.FrmHeader(this.page_layout.head, this);
		
	// bg colour
	if(this.meta.colour) 
		this.layout.wrapper.style.backgroundColor = '#'+this.meta.colour.split(':')[1];
	
	// create fields
	this.setup_fields_std();
}

_f.Frm.prototype.setup_print = function() { 
	var l = []
	this.default_format = 'Standard';
	for(var key in locals['Print Format']) {
		if(locals['Print Format'][key].doc_type == this.meta.name) {
			l.push(locals['Print Format'][key].name);
		}
	}

	// if default print format is given, use it
	if(this.meta.default_print_format)
		this.default_format = this.meta.default_print_format;

	l.push('Standard');
	this.print_sel = $a(null, 'select', '', {width:'160px'});
	add_sel_options(this.print_sel, l);
	this.print_sel.value = this.default_format;
}

_f.Frm.prototype.print_doc = function() {
	if(this.doc.docstatus==2)  {
		msgprint("Cannot Print Cancelled Documents.");
		return;
	}

	_p.show_dialog(); // multiple options
}

// ======================================================================================

_f.Frm.prototype.email_doc = function() {
	// make selector
	if(!_e.dialog) _e.make();
	
	_e.dialog.widgets['To'].value = '';
	
	if (cur_frm.doc && cur_frm.doc.contact_email) {
		_e.dialog.widgets['To'].value = cur_frm.doc.contact_email;
	}
	
	// set print selector
	sel = this.print_sel;
	var c = $td(_e.dialog.rows['Format'].tab,0,1);
	
	if(c.cur_sel) {
		c.removeChild(c.cur_sel);
		c.cur_sel = null;
	}
	c.appendChild(this.print_sel);
	c.cur_sel = this.print_sel;

	// hide / show attachments
	_e.dialog.widgets['Send With Attachments'].checked = 0;
	if(cur_frm.doc.file_list) {
		$ds(_e.dialog.rows['Send With Attachments']);
	} else {
		$dh(_e.dialog.rows['Send With Attachments']);
	}

	_e.dialog.widgets['Subject'].value = get_doctype_label(this.meta.name) + ': ' + this.docname;
	_e.dialog.show();
}

// ======================================================================================

_f.Frm.prototype.rename_notify = function(dt, old, name) {	
	// from form
	if(this.meta.in_dialog) 
		return;
	
	if(this.docname == old)
		this.docname = name;
	else
		return; // thats it, not for children!

	// editable
	this.is_editable[name] = this.is_editable[old];
	delete this.is_editable[old];

	// cleanup
	if(this && this.opendocs[old]) {
		// local doctype copy
		local_dt[dt][name] = local_dt[dt][old];
		local_dt[dt][old] = null;
	}

	delete this.opendocs[old];
	this.opendocs[name] = true;
	
	wn.re_route[window.location.hash] = '#Form/' + encodeURIComponent(this.doctype) + '/' + encodeURIComponent(name);
	wn.set_route('Form', this.doctype, name);
}

// SETUP
// ======================================================================================


_f.Frm.prototype.setup_meta = function() {
	this.meta = get_local('DocType',this.doctype);
	this.perm = get_perm(this.doctype); // for create
	if(this.meta.istable) { this.meta.in_dialog = 1 }
	this.setup_print();
}


// --------------------------------------------------------------------------------------

_f.Frm.prototype.setup_sidebar = function() {
	this.sidebar = new wn.widgets.form.sidebar.Sidebar(this);
}

// --------------------------------------------------------------------------------------

_f.Frm.prototype.setup_footer = function() {
	var me = this;
	
	// footer toolbar
	var f = this.page_layout.footer;

	// save buttom
	f.save_area = $a(this.page_layout.footer,'div','',{display:'none', marginTop:'11px'});
	f.help_area = $a(this.page_layout.footer,'div');

	var b = $btn(f.save_area, 'Save',
		function() { cur_frm.save('Save'); },{marginLeft:'0px'},'green');
	
	// show / hide save
	f.show_save = function() {
		$ds(me.page_layout.footer.save_area);
	}

	f.hide_save = function() {
		$dh(me.page_layout.footer.save_area);
	}
}

// --------------------------------------------------------------------------------------

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
		if((f.fieldtype=='Section Break')&&(fl[i+1])&&(fl[i+1].fieldtype!='Column Break')&&!f.hidden) {
			var c = this.layout.addcell();
			$y(c.wrapper, {padding: '8px'});			
		}
	}
}

// --------------------------------------------------------------------------------------
_f.Frm.prototype.add_custom_button = function(label, fn, icon) {
	this.frm_head.appframe.add_button(label, fn, icon);
}
_f.Frm.prototype.clear_custom_buttons = function() {
	this.frm_head.refresh_toolbar()
}

// --------------------------------------------------------------------------------------

_f.Frm.prototype.add_fetch = function(link_field, src_field, tar_field) {
	if(!this.fetch_dict[link_field]) {
		this.fetch_dict[link_field] = {'columns':[], 'fields':[]}
	}
	this.fetch_dict[link_field].columns.push(src_field);
	this.fetch_dict[link_field].fields.push(tar_field);
}

// --------------------------------------------------------------------------------------

_f.Frm.prototype.setup_client_script = function() {
	// setup client obj

	if(this.meta.client_script_core || this.meta.client_script || this.meta.__js) {
		this.runclientscript('setup', this.doctype, this.docname);
	}
}

// --------------------------------------------------------------------------------------

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
	_p.build(this.default_format, print_callback, null, 1);
}



// --------------------------------------------------------------------------------------

_f.Frm.prototype.show_the_frm = function() {
	// show the dialog
	if(this.meta.in_dialog && !this.parent.dialog.display) {
		if(!this.meta.istable)
			this.parent.table_form = false;
		this.parent.dialog.show();
	}	
}

// --------------------------------------------------------------------------------------
_f.Frm.prototype.set_print_heading = function(txt) {
	this.pformat[cur_frm.docname] = txt;
}

// --------------------------------------------------------------------------------------

_f.Frm.prototype.defocus_rest = function() {
	// deselect others
	if(_f.cur_grid_cell) _f.cur_grid_cell.grid.cell_deselect();
}

// -------- Permissions -------
// Returns global permissions, at all levels
// ======================================================================================

_f.Frm.prototype.get_doc_perms = function() {
	var p = [0,0,0,0,0,0];
	for(var i=0; i<this.perm.length; i++) {
		if(this.perm[i]) {
			if(this.perm[i][READ]) p[READ] = 1;
			if(this.perm[i][WRITE]) p[WRITE] = 1;
			if(this.perm[i][SUBMIT]) p[SUBMIT] = 1;
			if(this.perm[i][CANCEL]) p[CANCEL] = 1;
			if(this.perm[i][AMEND]) p[AMEND] = 1;
		}
	}
	return p;
}

// refresh
// ======================================================================================
_f.Frm.prototype.refresh_header = function() {
	// set title
	// main title
	if(!this.meta.in_dialog) {
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

// --------------------------------------------------------------------------------------

_f.Frm.prototype.check_doc_perm = function() {
	// get perm
	var dt = this.parent_doctype?this.parent_doctype : this.doctype;
	var dn = this.parent_docname?this.parent_docname : this.docname;
	this.perm = get_perm(dt, dn);
	this.orig_perm = get_perm(dt, dn, 1);
				  
	if(!this.perm[0][READ]) { 
		if(user=='Guest') {
			// allow temp access? via encryted akey
			if(_f.temp_access[dt] && _f.temp_access[dt][dn]) {
				this.perm = [[1,0,0]]
				return 1;
			}
		}
		window.back();
		return 0;
	}
	return 1
}

// --------------------------------------------------------------------------------------

_f.Frm.prototype.refresh = function(docname) {
	// record switch
	if(docname) {
		if(this.docname != docname && !this.meta.in_dialog && !this.meta.istable) scroll(0, 0);
		this.docname = docname;
	}
	if(!this.meta.istable) {
		cur_frm = this;
		this.parent.cur_frm = this;
	}
			
	if(this.docname) { // document to show

		// check permissions
		if(!this.check_doc_perm()) return;

		// do setup
		if(!this.setup_done) this.setup();

		// set customized permissions for this record
		this.runclientscript('set_perm',this.doctype, this.docname);

		// set the doc
		this.doc = get_local(this.doctype, this.docname);	  
		
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
		
		if(!this.doc.__archived && (this.editable || (!this.editable && this.meta.istable))) {
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
			// $(docuemnt).bind('form_refresh', function() { })
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

// --------------------------------------------------------------------------------------

_f.Frm.prototype.refresh_footer = function() {
	var f = this.page_layout.footer;
	if(f.save_area) {
		if(get_url_arg('embed') || (this.editable && !this.meta.in_dialog && this.doc.docstatus==0 && !this.meta.istable && this.get_doc_perms()[WRITE])) {
			f.show_save();
		} else {
			f.hide_save();
		}
	}
}

// --------------------------------------------------------------------------------------

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
			f.df = get_field(this.doctype, fn, this.docname);
			
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

// --------------------------------------------------------------------------------------

_f.Frm.prototype.cleanup_refresh = function() {
	var me = this;
	if(me.fields_dict['amended_from']) {
		if (me.doc.amended_from) {
			unhide_field('amended_from'); unhide_field('amendment_date');
		} else {
			hide_field('amended_from'); hide_field('amendment_date');
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
		set_field_permlevel(fn,1); // make it readonly / hidden
	}
}

// Resolve "depends_on" and show / hide accordingly
// ======================================================================================

_f.Frm.prototype.refresh_dependency = function() {
	var me = this;
	var doc = locals[this.doctype][this.docname];

	// build dependants' dictionary	
	var dep_dict = {};
	var has_dep = false;
	
	for(fkey in me.fields) { 
		var f = me.fields[fkey];
		f.dependencies_clear = true;
		var guardian = f.df.depends_on;
		if(guardian) {
			if(!dep_dict[guardian])
				dep_dict[guardian] = [];
			dep_dict[guardian][dep_dict[guardian].length] = f;
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
				if(v || (v==0 && !v.substr)) { 
					// guardian has value
				} else { 
					f.guardian_has_value = false;
				}
			}

			// show / hide
			if(f.guardian_has_value) {
				if(f.grid)f.grid.show(); else $ds(f.wrapper);		
			} else {
				if(f.grid)f.grid.hide(); else $dh(f.wrapper);		
			}
		}
	}
}

// setnewdoc is called when a record is loaded for the first time
// ======================================================================================

_f.Frm.prototype.setnewdoc = function(docname) {
	this.check_doctype_conflict(docname);

	// if loaded
	if(this.opendocs[docname]) { // already exists
		this.docname=docname;
		return;
	}

	//if(!this.meta)
	//	this.setup_meta();

	// make a copy of the doctype for client script settings
	// each record will have its own client script
	Meta.make_local_dt(this.doctype,docname);

	this.docname = docname;
	var me = this;
	
	var viewname = docname;
	if(this.meta.issingle) viewname = this.doctype;

	// Client Script
	this.runclientscript('onload', this.doctype, this.docname);
	
	this.is_editable[docname] = 1;
	if(this.meta.read_only_onload) this.is_editable[docname] = 0;
		
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

// ======================================================================================
var validated; // bad design :(
_f.Frm.prototype.save = function(save_action, call_back) {
	//alert(save_action);
	if(!save_action) save_action = 'Save';
	var me = this;
	if(this.savingflag) {
		msgprint("Document is currently saving....");
		return; // already saving (do not double save)
	}

	if(save_action=='Submit') {
		locals[this.doctype][this.docname].submitted_on = dateutil.full_str();
		locals[this.doctype][this.docname].submitted_by = user;
	}
	
	if(save_action=='Trash') {
		var reason = prompt('Reason for trash (mandatory)', '');
		if(!strip(reason)) {
			msgprint('Reason is mandatory, not trashed');
			return;
		}
		locals[this.doctype][this.docname].trash_reason = reason;
	}

	// run validations
	if(save_action=='Cancel') {
		var reason = prompt('Reason for cancellation (mandatory)', '');
		if(!strip(reason)) {
			msgprint('Reason is mandatory, not cancelled');
			return;
		}
		locals[this.doctype][this.docname].cancel_reason = reason;
		locals[this.doctype][this.docname].cancelled_on = dateutil.full_str();
		locals[this.doctype][this.docname].cancelled_by = user;
	} else if(save_action=='Update') {
		// no validation for update
	} else { // no validation for cancellation
		validated = true;
		if(this.cscript.validate)
			this.runclientscript('validate', this.doctype, this.docname);
	
		if(!validated) {
			this.savingflag = false;
			return 'Error';
		}
	}
 	
	
	var ret_fn = function(r) {
		me.savingflag = false;
		if(user=='Guest' && !r.exc) {
			// if user is guest, show a message after succesful saving
			$dh(me.page_layout.wrapper);
			$ds(me.saved_wrapper);
			me.saved_wrapper.innerHTML = 
				'<div style="padding: 150px 16px; text-align: center; font-size: 14px;">' 
				+ (cur_frm.message_after_save ? cur_frm.message_after_save : 'Your information has been sent. Thank you!') 
				+ '</div>';
			return; // no refresh
		}
		
		if(!me.meta.istable) {
			me.refresh(r.docname);
		}

		if(call_back){
			call_back(r);
		}
	}

	var me = this;
	var ret_fn_err = function(r) {
		var doc = locals[me.doctype][me.docname];
		me.savingflag = false;
		ret_fn(r);
	}
	
	this.savingflag = true;
	if(this.docname && validated) {
		// scroll to top
		scroll(0, 0);
		
		return this.savedoc(save_action, ret_fn, ret_fn_err);
	}
}

// ======================================================================================

_f.Frm.prototype.runscript = function(scriptname, callingfield, onrefresh) {
	var me = this;
	if(this.docname) {
		// make doc list
		var doclist = compress_doclist(make_doclist(this.doctype, this.docname));
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


// ======================================================================================

_f.Frm.prototype.runclientscript = function(caller, cdt, cdn) {
	var _dt = this.parent_doctype ? this.parent_doctype : this.doctype;
	var _dn = this.parent_docname ? this.parent_docname : this.docname;
	var doc = get_local(_dt, _dn);

	if(!cdt)cdt = this.doctype;
	if(!cdn)cdn = this.docname;

	var ret = null;
	try {
		if(this.cscript[caller])
			ret = this.cscript[caller](doc, cdt, cdn);
		// for product
		if(this.cscript['custom_'+caller])
			ret += this.cscript['custom_'+caller](doc, cdt, cdn);
	} catch(e) {
		console.log(e);
	}

	if(caller && caller.toLowerCase()=='setup') {

		var doctype = get_local('DocType', this.doctype);
		
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

// ======================================================================================

_f.Frm.prototype.copy_doc = function(onload, from_amend) {
	
	if(!this.perm[0][CREATE]) {
		msgprint('You are not allowed to create '+this.meta.name);
		return;
	}
	
	var dn = this.docname;
	// copy parent
	var newdoc = LocalDB.copy(this.doctype, dn, from_amend);

	// do not copy attachments
	if(this.meta.allow_attach && newdoc.file_list)
		newdoc.file_list = null;
	
	// copy chidren
	var dl = make_doclist(this.doctype, dn);

	// table fields dict - for no_copy check
	var tf_dict = {};

	for(var d in dl) {
		d1 = dl[d];
		
		// get tabel field
		if(!tf_dict[d1.parentfield]) {
			tf_dict[d1.parentfield] = get_field(d1.parenttype, d1.parentfield);
		}
		
		if(d1.parent==dn && cint(tf_dict[d1.parentfield].no_copy)!=1) {
			var ch = LocalDB.copy(d1.doctype, d1.name, from_amend);
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

// ======================================================================================

_f.Frm.prototype.reload_doc = function() {
	this.check_doctype_conflict(this.docname);

	var me = this;
	var ret_fn = function(r, rtxt) {
		// n tweets and last comment				
		me.runclientscript('setup', me.doctype, me.docname);
		me.refresh();
	}

	if(me.doc.__islocal) { 
		// reload only doctype
		$c('webnotes.widgets.form.load.getdoctype', {'doctype':me.doctype }, ret_fn, null, null, 'Refreshing ' + me.doctype + '...');
	} else {
		// delete all unsaved rows
		var gl = me.grids;
		for(var i = 0; i < gl.length; i++) {
			var dt = gl[i].df.options;
			for(var dn in locals[dt]) {
				if(locals[dt][dn].__islocal && locals[dt][dn].parent == me.docname) {
					var d = locals[dt][dn];
					d.parent = '';
					d.docstatus = 2;
					d.__deleted = 1;
				}
			}
		}
		// reload doc and docytpe
		$c('webnotes.widgets.form.load.getdoc', {'name':me.docname, 'doctype':me.doctype, 'getdoctype':1, 'user':user}, ret_fn, null, null, 'Refreshing ' + me.docname + '...');
	}
}

// ======================================================================================

_f.Frm.prototype.savedoc = function(save_action, onsave, onerr) {
	this.error_in_section = 0;
	save_doclist(this.doctype, this.docname, save_action, onsave, onerr);
}

_f.Frm.prototype.saveupdate = function() {
	this.save('Update');
}

_f.Frm.prototype.savesubmit = function() {
	var answer = confirm("Permanently Submit "+this.docname+"?");
	var me = this;
	if(answer) {
		this.save('Submit', function(r) {
			if(!r.exc && me.cscript.on_submit) {
				me.runclientscript('on_submit', me.doctype, me.docname);
			}
		});
	}
}

_f.Frm.prototype.savecancel = function() {
	var answer = confirm("Permanently Cancel "+this.docname+"?");
	if(answer) this.save('Cancel');
}

// delete the record
_f.Frm.prototype.savetrash = function() {
	var me = this;
	var answer = confirm("Permanently Delete "+this.docname+"? This action cannot be reversed");
	if(answer) {
		$c('webnotes.model.delete_doc', {dt:this.doctype, dn:this.docname}, function(r,rt) {
			if(r.message=='okay') {
				// delete from locals
				LocalDB.delete_doc(me.doctype, me.docname);
				
				// delete from recent
				if(wn.ui.toolbar.recent) wn.ui.toolbar.recent.remove(me.doctype, me.docname);
				
				// "close"
				window.back();
			}
		})
	} 
}

// ======================================================================================

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

// ======================================================================================

_f.get_value = function(dt, dn, fn) {
	if(locals[dt] && locals[dt][dn]) 
		return locals[dt][dn][fn];
}

_f.set_value = function(dt, dn, fn, v) {
	var d = locals[dt][dn];

	if(!d) {
		console.log('_f.set_value - '+ fn+': "'+dt+','+dn+'" not found');
		return;
	}

	var changed = d[fn] != v;
	if(changed && (d[fn]==null || v==null) && (cstr(d[fn])==cstr(v))) changed = 0;

	if(changed) {
		var prev_unsaved = d.__unsaved
		d[fn] = v;
		d.__unsaved = 1;
			
		if(d.parent && d.parenttype) {
			var doc = locals[d.parenttype][d.parent];
			doc.__unsaved = 1;
			var frm = wn.views.formview[d.parenttype].frm;
		} else {
			var doc = locals[d.doctype][d.name]
			doc.__unsaved = 1;
			var frm = wn.views.formview[d.doctype] && wn.views.formview[d.doctype].frm;
		}
		
		// No need to refresh labels and toolbar again and again.
		// Just check if __unsaved was not set previously
		if(frm && frm==cur_frm && frm.frm_head && !prev_unsaved) {
			frm.frm_head.refresh_labels();
			//frm.frm_head.refresh_toolbar();
		}
	}
}

// ======================================================================================

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

