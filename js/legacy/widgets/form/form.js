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
							+ this.tip_wrapper
							+ this.body
								+ this.layout
								+ this.footer
						+ this.sidebar
				+ this.print_wrapper
					+ this.head
*/

// called from table edit
_f.edit_record = function(dt, dn) {
	d = _f.frm_dialog;
	
	var show_dialog = function() {
		var f = frms[dt];
		if(f.meta.istable) {
			f.parent_doctype = cur_frm.doctype;
			f.parent_docname = cur_frm.docname;
		}
		
		d.cur_frm = f;
		d.dn = dn;
		d.table_form = f.meta.istable;
		
		// show the form
		f.refresh(dn);
	}

	// load
	if(!frms[dt]) {
		_f.add_frm(dt, show_dialog, null);
	} else {
		show_dialog();
	}
	
}

_f.Frm = function(doctype, parent) {
	this.docname = '';
	this.doctype = doctype;
	this.display = 0;
		
	var me = this;
	this.is_editable = {};
	this.opendocs = {};
	this.cur_section = {};
	this.sections = [];
	this.sections_by_label = {};
	this.section_count;
	this.grids = [];
	this.cscript = {};
	this.pformat = {};
	this.fetch_dict = {};
	this.parent = parent;
	this.tinymce_id_list = [];
	
	frms[doctype] = this;

	this.setup_meta(doctype);
	
	// notify on rename
	rename_observers.push(this);
}

// ======================================================================================

_f.Frm.prototype.setup = function() {

	var me = this;
	this.fields = [];
	this.fields_dict = {};

	// wrapper
	this.wrapper = $a(this.parent.body, 'div');
	
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
	this.print_body = $a(this.print_wrapper,'div', 'layout_wrapper', {padding:'23px'});
	
	var t= make_table(this.print_head, 1 ,2, '100%', [], {padding: '6px'});
	this.view_btn_wrapper = $a($td(t,0,0) , 'span', 'green_buttons');
	this.view_btn = $btn(this.view_btn_wrapper, 'View Details', function() { cur_frm.edit_doc() }, 
		{marginRight:'4px'}, 'green');

	this.print_btn = $btn($td(t,0,0), 'Print', function() { cur_frm.print_doc() });

	$y($td(t,0,1), {textAlign: 'right'});
	this.print_close_btn = $btn($td(t,0,1), 'Close', function() { nav_obj.show_last_open(); });
}


_f.Frm.prototype.onhide = function() { if(_f.cur_grid_cell) _f.cur_grid_cell.grid.cell_deselect(); }

// ======================================================================================

_f.Frm.prototype.setup_std_layout = function() {
	this.page_layout = new wn.PageLayout({
		parent: this.wrapper,
		main_width: this.in_dialog ? '100%' : '75%',
		sidebar_width: this.in_dialog ? '0%' : '25%'
	})	
	
	
	this.tip_wrapper = $a(this.page_layout.toolbar_area, 'div');		
		
	// only tray
	this.meta.section_style='Simple'; // always simple!
	
	// layout
	this.layout = new Layout(this.page_layout.body, '100%');
	
	// sidebar
	if(!this.in_dialog) {
		this.setup_sidebar();
	}
		
	// footer
	this.setup_footer();		
	
		
	// header - no headers for tables and guests
	if(!(this.meta.istable || user=='Guest')) this.frm_head = new _f.FrmHeader(this.page_layout.head, this);
	
	// hide close btn for dialog rendering
	if(this.frm_head && this.meta.in_dialog) $dh(this.frm_head.page_head.close_btn);
	
	// setup tips area
	this.setup_tips();
	
	// bg colour
	if(this.meta.colour) 
		this.layout.wrapper.style.backgroundColor = '#'+this.meta.colour.split(':')[1];
	
	// create fields
	this.setup_fields_std();
}

// ======================================================================================

_f.Frm.prototype.setup_print = function() { 
	var fl = getchildren('DocFormat', this.meta.name, 'formats', 'DocType');
	var l = [];	
	this.default_format = 'Standard';
	if(fl.length) {
		this.default_format = fl[0].format;
		for(var i=0;i<fl.length;i++) 
			l.push(fl[i].format);
		
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
	if(this.doctype != dt) return;
	
	// sections
	this.cur_section[name] = this.cur_section[old];
	delete this.cur_section[old];

	// editable
	this.is_editable[name] = this.is_editable[old];
	delete this.is_editable[old];

	// from form
	if(this.docname == old)
		this.docname = name;	

	// cleanup

	if(this && this.opendocs[old]) {
		// local doctype copy
		local_dt[dt][name] = local_dt[dt][old];
		local_dt[dt][old] = null;
	}
	
	this.opendocs[old] = false;
	this.opendocs[name] = true;
}
// refresh the heading labels
// ======================================================================================

_f.Frm.prototype.set_heading = function() {
	if(!this.meta.istable && this.frm_head) this.frm_head.refresh_labels(this);
}


// PAGING
// ======================================================================================

_f.Frm.prototype.set_section = function(sec_id) {
	if(!this.sections[sec_id] || !this.sections[sec_id].expand) 
		return; // Simple type
	
	if(this.sections[this.cur_section[this.docname]])
		this.sections[this.cur_section[this.docname]].collapse();
	this.sections[sec_id].expand();
	this.cur_section[this.docname] = sec_id;
}

// TIPS
// ======================================================================================

_f.Frm.prototype.setup_tips = function() {
	var me = this;
	this.tip_box = $a(this.tip_wrapper, 'div', 'help_box');

	var tab = $a(this.tip_box, 'table');
	var r = tab.insertRow(0);
	var c0 = r.insertCell(0);
	this.c1 = r.insertCell(1);
	
	this.img = $a(c0, 'img');
	this.img.setAttribute('src','lib/images/icons/lightbulb.gif');
	c0.style.width = '24px';
	
	this.set_tip = function(t) {
		me.c1.innerHTML = '<div style="margin-bottom: 8px;">'+t+'</div>'; 
		$ds(me.tip_box);
	}
	this.append_tip = function(t) {
		me.c1.innerHTML += '<div style="margin-bottom: 8px;">' + t + '</div>';  $ds(me.tip_box);
	}
	this.clear_tip = function() { me.c1.innerHTML = ''; $dh(me.tip_box); }
	$dh(this.tip_box);
}

// SETUP
// ======================================================================================


_f.Frm.prototype.setup_meta = function() {
	this.meta = get_local('DocType',this.doctype);
	this.perm = get_perm(this.doctype); // for create
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
	f.save_area = $a(this.page_layout.footer,'div','',{display:'none'});
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
	var fl = fields_list[this.doctype]; 

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
		
		// no section breaks in embedded forms
		if(get_url_arg('embed') && (in_list(['Section Break','Column Break'], f.fieldtype))) continue;
		
		// if section break and next item 
		// is a section break then ignore
		if(f.fieldtype=='Section Break' && fl[i+1] && fl[i+1].fieldtype=='Section Break') continue;
		
		var fn = f.fieldname?f.fieldname:f.label;
				
		var fld = make_field(f, this.doctype, this.layout.cur_cell, this);
		this.fields[this.fields.length] = fld;
		this.fields_dict[fn] = fld;

		// Add to section break so that this section can be shown when there is an error
		if(this.meta.section_style != 'Simple')
			fld.parent_section = sec;
		
		if(f.fieldtype=='Section Break' && f.options != 'Simple')
			sec = fld;
		
		// default col-break after sec-break
		if((f.fieldtype=='Section Break')&&(fl[i+1])&&(fl[i+1].fieldtype!='Column Break')) {
			var c = this.layout.addcell();
			$y(c.wrapper, {padding: '8px'});			
		}
	}
}

// --------------------------------------------------------------------------------------
_f.Frm.prototype.add_custom_button = function(label, fn, icon) {
	this.frm_head.page_head.add_button(label, fn, 1);
}
_f.Frm.prototype.clear_custom_buttons = function() {
	//
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

// change the parent - deprecated
_f.Frm.prototype.set_parent = function(parent) {
	if(parent) {
		this.parent = parent;
		if(this.wrapper && this.wrapper.parentNode != parent)
			parent.appendChild(this.wrapper);
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


// SHOW!
// ======================================================================================

_f.Frm.prototype.hide = function() {
	$dh(this.wrapper);
	this.display = 0;
	if(hide_autosuggest)
		hide_autosuggest();
}

// --------------------------------------------------------------------------------------

_f.Frm.prototype.show_the_frm = function() {
	// hide other (open) forms
	if(this.parent.last_displayed && this.parent.last_displayed != this) {
		this.parent.last_displayed.defocus_rest();
		this.parent.last_displayed.hide();
	}

	// show the form
	if(this.wrapper && this.wrapper.style.display.toLowerCase()=='none') {
		$ds(this.wrapper);
		this.display = 1;
	}
	
	// show the dialog
	if(this.meta.in_dialog && !this.parent.dialog.display) {
		if(!this.meta.istable)
			this.parent.table_form = false;
		this.parent.dialog.show();
	}
	
	this.parent.last_displayed = this;
}

// --------------------------------------------------------------------------------------
_f.Frm.prototype.set_print_heading = function(txt) {
	this.pformat[cur_frm.docname] = txt;
}

// --------------------------------------------------------------------------------------

_f.Frm.prototype.defocus_rest = function() {
	// deselect others
	if(_f.cur_grid_cell) _f.cur_grid_cell.grid.cell_deselect();
	cur_page = null;
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

	// show / hide buttons
	if(this.frm_head)this.frm_head.refresh_toolbar();
	
	// add to recent
	if(wn.ui.toolbar.recent) wn.ui.toolbar.recent.add(this.doctype, this.docname, 1);
	
	// refresh_heading - status etc.
	this.set_heading();
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
		nav_obj.show_last_open();
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
		var is_onload = false;
		if(!this.opendocs[this.docname]) { 
			is_onload = true;
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
			$(document).trigger('form_refresh')
			
			// tabs
			this.refresh_tabs();
			
			// fields
			this.refresh_fields();
			
			// dependent fields
			this.refresh_dependency();

			// footer
			this.refresh_footer();
			
			// layout
			if(this.layout) this.layout.show();

			// call onload post render for callbacks to be fired
			if(is_onload)
				this.runclientscript('onload_post_render', this.doctype, this.docname);			
		
		} else {
			// show print layout
			// ----------------------------------
			this.refresh_header();
			if(this.print_wrapper) {
				this.refresh_print_layout();
			}
			this.runclientscript('edit_status_changed');
		}
		
		// show the record
		if(!this.display) this.show_the_frm();
		
		// show the page
		if(!this.meta.in_dialog) page_body.change_to('Forms');

		$(cur_frm.wrapper).trigger('render_complete');

	} 
}

// --------------------------------------------------------------------------------------

_f.Frm.prototype.refresh_tabs = function() {
	var me = this;
	if(me.meta.section_style=='Tray'||me.meta.section_style=='Tabbed') {
		for(var i in me.sections) {
			me.sections[i].collapse();
		}
		
		me.set_section(me.cur_section[me.docname]);
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
	// set fields
	for(var i=0; i<this.fields.length; i++) {
		var f = this.fields[i];
		f.perm = this.perm;
		f.docname = this.docname;
		if(f.refresh)f.refresh();
	}

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

	var iconsrc = 'page.gif';
	if(this.meta.smallicon) 
		iconsrc = this.meta.smallicon;

	// Client Script
	this.runclientscript('onload', this.doctype, this.docname);
	
	this.is_editable[docname] = 1;
	if(this.meta.read_only_onload) this.is_editable[docname] = 0;
		
	// Section Type
	if(this.meta.section_style=='Tray'||this.meta.section_style=='Tabbed') { this.cur_section[docname] = 0; }

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
			me.refresh();
		}

		if(call_back){
			if(call_back == 'home'){ loadpage('_home'); return; }
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
		if(callingfield)callingfield.input.disabled = true;

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
				if(callingfield)callingfield.input.done_working();
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
	var me = this;
	if(frms['DocType'] && frms['DocType'].opendocs[me.doctype]) {
		msgprint("error:Cannot refresh an instance of \"" + me.doctype+ "\" when the DocType is open.");
		return;
	}

	var ret_fn = function(r, rtxt) {
		page_body.set_status('Done')
		// n tweets and last comment
				
		me.runclientscript('setup', me.doctype, me.docname);
		me.refresh();
	}

	page_body.set_status('Reloading...')
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
				nav_obj.show_last_open();
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
		errprint('error:Trying to set a value for "'+dt+','+dn+'" which is not found');
		return;
	}

	var changed = d[fn] != v;
	if(changed && (d[fn]==null || v==null) && (cstr(d[fn])==cstr(v))) changed = 0;

	if(changed) {
		d[fn] = v;
		d.__unsaved = 1;
		var frm = frms[d.doctype];
		try {
			if(d.parent && d.parenttype) {
				locals[d.parenttype][d.parent].__unsaved = 1;
				frm = frms[d.parenttype];
			}
		} catch(e) {
			if(d.parent && d.parenttype)
			errprint('Setting __unsaved error:'+d.name+','+d.parent+','+d.parenttype);
		}
		if(frm && frm==cur_frm) {
			frm.set_heading();
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

