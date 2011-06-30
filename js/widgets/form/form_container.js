_f.FrmContainer = function() {
	this.wrapper = page_body.add_page("Forms", function() {}, function() { });
	this.last_displayed = null;
	
	// create hidden
	$dh(this.wrapper);

	this.body = $a(this.wrapper,'div','frm_container');
		
	// make by twin
	_f.frm_dialog = new _f.FrmDialog();
}


// FrmDialog - twin of FrmContainer
// =======================================================================
_f.frm_dialog = null;
_f.calling_doc_stack = [];
_f.temp_access = {};

_f.FrmDialog = function() {
	var me = this;
	this.last_displayed = null;

	var d = new Dialog(640, null, 'Edit Row');
	this.body = $a(d.body, 'div', 'dialog_frm');
	$y(d.body, {backgroundColor:'#EEE'});
	d.done_btn_area = $a(d.body, 'div', '', {margin:'8px'});

	// done button
	me.on_complete = function() { 

		if(me.table_form) {
			// table form, just hide the dialog (saving will be done with the parent)
			me.dialog.hide();
		} else {
			// form in dialog, so save it
			var callback = function(r) {
				var dn = cur_frm.docname;
				if(!r.exc) {
					// check if there is another dialog open?
					me.dialog.hide();
				}

				// callback
				if(me.on_save_callback)
					me.on_save_callback(dn);
			}
			cur_frm.save('Save', callback);
		}
	}

	// set title onshow
	// -------------------------------------------
	d.onshow = function() {
		// set the dialog title
		d.done_btn_area.innerHTML = '';
		d.done_btn = $btn(d.done_btn_area, 'Save', null, null, 'green');
		d.done_btn.onclick = function() { me.on_complete() };
		if(me.table_form) {
			d.set_title("Editing Row #" + (_f.cur_grid_ridx+1));
			d.done_btn.innerHTML = 'Done Editing';
		} else {
			d.set_title(cur_frm.doctype==cur_frm.doctype ? (cur_frm.doctype) : (cur_frm.doctype + ': ' + cur_frm.docname));
			d.done_btn.innerHTML = 'Save';
		}
	}

	// on hide, refresh grid or call onsave
	// -------------------------------------------
	d.onhide = function() {
		// if called from grid, refresh the row
		if(_f.cur_grid)
			_f.cur_grid.refresh_row(_f.cur_grid_ridx, me.dn);
		
		// set the new global cur_frm (if applicable)
		if(page_body.cur_page_label = 'Forms') {
			cur_frm = _f.frm_con.cur_frm;
		}
	}
	this.dialog = d;
}

// Form Factory
// =======================================================================
_f.add_frm = function(doctype, onload, opt_name, from_archive) {	
	// dont open doctype and docname from the same session
	if(frms['DocType'] && frms['DocType'].opendocs[doctype]) {
		msgprint("error:Cannot create an instance of \"" + doctype+ "\" when the DocType is open.");
		return;
	}

	// form already created, done
	if(frms[doctype]) { 
		return frms[doctype]; 
	}

	// Load Doctype from server
	var callback = function(r,rt) {
		page_body.set_status('Done')

		if(!locals['DocType'][doctype]) {
			if(r.exc) { msgprint("Did not load " + doctype, 1); }
			loadpage('_home');
			return;
		}
		
		if(r.print_access) {
			if(!_f.temp_access[doctype])
				_f.temp_access[doctype] = {};
			_f.temp_access[doctype][opt_name] = 1;	
		}
		
		
		// show fullpage or in Dialog?
		var meta = locals['DocType'][doctype];
		var in_dialog = false;
		
		// if is table, its in the Dialog!
		if(meta.istable) meta.in_dialog = 1;
		
		if(cint(meta.in_dialog)) {
			var parent = _f.frm_dialog;	
			in_dialog = true;
		} else {
			var parent = _f.frm_con;
		}
		
		// create the object
		var f = new _f.Frm(doctype, parent);
		f.in_dialog = in_dialog;
		
		if(onload)onload(r,rt);
	}
	
	// check if record is new (called from mapper etc)
	var is_new = 0;
	if(opt_name && locals[doctype] && locals[doctype][opt_name] && locals[doctype][opt_name].__islocal) {
		is_new = 1;
	}
	
	if(opt_name && !is_new) {
		// get both
		var args = {'name':opt_name, 'doctype':doctype, 'getdoctype':1, 'user':user};

		if(get_url_arg('akey')) args['akey'] = get_url_arg('akey');
		if(from_archive) args['from_archive'] = 1;

		$c('webnotes.widgets.form.getdoc', args, callback);
	} else {
		// get doctype only
		$c('webnotes.widgets.form.getdoctype', args={'doctype':doctype}, callback);
	}
}


