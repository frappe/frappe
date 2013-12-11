// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

/* Form page structure

	+ this.parent (either FormContainer or Dialog)
 		+ this.wrapper
			+ this.toolbar
			+ this.form_wrapper
					+ this.head
					+ this.body
						+ this.layout
				+ this.sidebar
			+ this.footer
*/

wn.provide('_f');
wn.provide('wn.ui.form');

wn.ui.form.Controller = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.setup && this.setup();
	}
});

_f.frms = {};

_f.Frm = function(doctype, parent, in_form) {
	this.docname = '';
	this.doctype = doctype;
	this.display = 0;
	this.refresh_if_stale_for = 120;
		
	var me = this;
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
	$(document).on('rename', function(event, dt, old_name, new_name) {
		if(dt==me.doctype)
			me.rename_notify(dt, old_name, new_name)
	});
}

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
	this.state_fieldname = wn.workflow.get_state_fieldname(this.doctype);
	
	// wrapper
	this.wrapper = this.parent;
	wn.ui.make_app_page({
		parent: this.wrapper,
		single_column: true
	});
	this.appframe = this.wrapper.appframe;
	this.layout_main = $(this.wrapper)
		.find(".layout-main")
		.css({"padding-bottom": "0px"})
		.get(0);
	
	this.toolbar = new wn.ui.form.Toolbar({
		frm: this,
		appframe: this.appframe
	});
	this.frm_head = this.toolbar;
		
	// print layout
	this.setup_print_layout();
		
	// 2 column layout
	this.setup_std_layout();

	// client script must be called after "setup" - there are no fields_dict attached to the frm otherwise
	this.script_manager = new wn.ui.form.ScriptManager({
		frm: this
	});
	this.script_manager.setup();
	this.watch_model_updates();
		
	this.footer = new wn.ui.form.Footer({
		frm: this,
		parent: $(this.wrapper).find(".appframe-footer")
	})
	
	
	this.setup_done = true;
}

_f.Frm.prototype.setup_print_layout = function() {
	this.print_wrapper = $('<div>\
		<div class="print-toolbar row" style="background-color: #eee; \
			padding-top: 5px; padding-bottom: 5px; margin-top: -15px; \
			margin-bottom: 15px; padding-left: 15px; position:relative;">\
			<i class="text-muted icon-print" style="position: absolute; top: 13px; left: 10px; "></i>\
			<div class="col-xs-3">\
				<select class="print-preview-select form-control"></select></div>\
			<div class="col-xs-3" style="padding-top: 7px;">\
				<input type="checkbox" class="print-letterhead" checked/> Letterhead</div>\
			<div class="col-xs-6 text-right" style="padding-top: 7px;">\
				<a style="margin-right: 7px;" class="print-print">Print</a>\
				<a class="close">×</a>\
			</div>\
		</div>\
		<div class="print-preview">\
		</div>\
	</div>')
		.appendTo(this.layout_main)
		.toggle(false);
	
	var me = this;
	this.print_wrapper.find(".close").click(function() {
		me.hide_print();
	});
	
	this.print_formats = wn.meta.get_print_formats(this.meta.name);
	this.print_letterhead = this.print_wrapper
		.find(".print-letterhead")
		.on("change", function() { me.print_sel.trigger("change"); });
	this.print_sel = this.print_wrapper
		.find(".print-preview-select")
		.on("change", function() {
			 _p.build(me.print_sel.val(), function(html) {
				 me.print_wrapper.find(".print-preview").html(html);
			 }, !me.print_letterhead.is(":checked"), true, true);
		})
		
	this.print_wrapper.find(".print-print").click(function() {
		_p.build(
			me.print_sel.val(), // fmtname
			_p.go, // onload
			!me.print_letterhead.is(":checked") // no_letterhead
		);
	})
}

_f.Frm.prototype.print_doc = function() {
	if(this.print_wrapper.is(":visible")) {
		this.hide_print();
		return;
	}
	if(this.doc.docstatus==2)  {
		msgprint("Cannot Print Cancelled Documents.");
		return;
	}
	this.print_wrapper.toggle(true);
	this.print_sel
		.empty().add_options(this.print_formats)
		.trigger("change");
	
	this.form_wrapper.toggle(false);
}

_f.Frm.prototype.hide_print = function() {
	if(this.setup_done) {
		this.print_wrapper.toggle(false);
		this.form_wrapper.toggle(true);
	}
}

_f.Frm.prototype.watch_model_updates = function() {
	// watch model updates
	var me = this;

	// on main doc
	wn.model.on(me.doctype, "*", function(fieldname, value, doc) {
		// set input
		if(doc.name===me.docname) {
			me.dirty();
			me.fields_dict[fieldname] 
				&& me.fields_dict[fieldname].refresh(fieldname);
			me.refresh_dependency();
			me.script_manager.trigger(fieldname, doc.doctype, doc.name);
		}
	})
	
	// on table fields
	$.each(wn.model.get("DocField", {fieldtype:"Table", parent: me.doctype}), function(i, df) {
		wn.model.on(df.options, "*", function(fieldname, value, doc) {
			if(doc.parent===me.docname && doc.parentfield===df.fieldname) {
				me.dirty();
				me.fields_dict[df.fieldname].grid.set_value(fieldname, value, doc);
				me.script_manager.trigger(fieldname, doc.doctype, doc.name);
			}
		})
	})
	
}

_f.Frm.prototype.onhide = function() { 
	if(_f.cur_grid_cell) _f.cur_grid_cell.grid.cell_deselect(); 
}

_f.Frm.prototype.setup_std_layout = function() {
	this.form_wrapper = $('<div></div>').appendTo(this.layout_main);
	this.body_header	= $("<div>").appendTo(this.form_wrapper);
	this.body 			= $("<div>").appendTo(this.form_wrapper);

	// only tray
	this.meta.section_style='Simple'; // always simple!
	
	// layout
	this.layout = new wn.ui.form.Layout({
		parent: this.body,
		doctype: this.doctype,
		frm: this,
	});
	this.layout.make();
	
	this.fields_dict = this.layout.fields_dict;
	this.fields = this.layout.fields_list;

	this.dashboard = new wn.ui.form.Dashboard({
		frm: this,
	});
	
	// state
	this.states = new wn.ui.form.States({
		frm: this
	});
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

// rename the form
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

	if(wn.ui.toolbar.recent)
		wn.ui.toolbar.recent.add(this.doctype, this.docname, 1);
	
	// show / hide buttons
	if(this.frm_head) {
		this.frm_head.refresh();
	}
}

_f.Frm.prototype.check_doc_perm = function() {
	// get perm
	var dt = this.parent_doctype?this.parent_doctype : this.doctype;
	var dn = this.parent_docname?this.parent_docname : this.docname;
	this.perm = wn.perm.get_perm(dt, dn);
				  
	if(!this.perm[0][READ]) { 
		return 0;
	}
	return 1
}

_f.Frm.prototype.refresh = function(docname) {
	// record switch
	if(docname) {
		if(this.docname != docname && (!this.meta.in_dialog || this.in_form) && 
			!this.meta.istable) {
				scroll(0, 0);
				this.hide_print();
			}
		this.docname = docname;
	}

	cur_frm = this;
	
	if(this.docname) { // document to show

		// check permissions
		if(!this.check_doc_perm()) return;

		// read only (workflow)
		this.read_only = wn.workflow.is_read_only(this.doctype, this.docname);

		// set the doc
		this.doc = wn.model.get_doc(this.doctype, this.docname);	  
		
		// check if doctype is already open
		if (!this.opendocs[this.docname]) {
			this.check_doctype_conflict(this.docname);
		} else {
			if(this.doc && (!this.doc.__unsaved) && this.doc.__last_sync_on && 
				(new Date() - this.doc.__last_sync_on) > (this.refresh_if_stale_for * 1000)) {
				this.reload_doc();
				return;
			}
		}

		// do setup
		if(!this.setup_done) this.setup();
		
		// load the record for the first time, if not loaded (call 'onload')
		cur_frm.cscript.is_onload = false;
		if(!this.opendocs[this.docname]) { 
			cur_frm.cscript.is_onload = true;
			this.setnewdoc(); 
		} else {
			this.render_form();
		}

	} 
}

_f.Frm.prototype.render_form = function() {	
	if(!this.meta.istable) {
		// header
		this.refresh_header();

		// call trigger
		this.script_manager.trigger("refresh");
		
		// trigger global trigger
		// to use this
		$(document).trigger('form_refresh');
					
		// fields
		this.refresh_fields();
		
		// call onload post render for callbacks to be fired
		if(this.cscript.is_onload) {
			this.script_manager.trigger("onload_post_render");
		}
			
		// focus on first input
		
		if(this.doc.docstatus==0) {
			var first = this.form_wrapper.find('.form-layout-row :input:first');
			if(!in_list(["Date", "Datetime"], first.attr("data-fieldtype"))) {
				first.focus();
			}
		}
	
	} else {
		this.refresh_header();
	}

	$(cur_frm.wrapper).trigger('render_complete');
	
}

_f.Frm.prototype.refresh_field = function(fname) {
	cur_frm.fields_dict[fname] && cur_frm.fields_dict[fname].refresh
		&& cur_frm.fields_dict[fname].refresh();
}

_f.Frm.prototype.refresh_fields = function() {
	this.layout.refresh();
	this.layout.primary_button = $(this.wrapper).find(".btn-primary");

	// cleanup activities after refresh
	this.cleanup_refresh(this);
	
	// dependent fields
	this.refresh_dependency();
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
	
	if(me.meta.autoname=="naming_series:" && !me.doc.__islocal) {
		cur_frm.toggle_display("naming_series", false);
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
				f.guardian_has_value = me.script_manager.trigger(f.df.depends_on.substr(3), me.doctype, me.docname);
			} else {
				if(!v) {
					f.guardian_has_value = false;
				}
			}

			// show / hide
			if(f.guardian_has_value) {
				if(f.df.hidden_due_to_dependency) {
					f.df.hidden_due_to_dependency = false;
					f.refresh();
				}
			} else {
				if(!f.df.hidden_due_to_dependency) {
					f.df.hidden_due_to_dependency = true;
					f.refresh();
				}
			}
		}
	}
	
	this.layout.refresh_section_count();
}

_f.Frm.prototype.setnewdoc = function() {
	// moved this call to refresh function
	// this.check_doctype_conflict(docname);
	var me = this;

	this.script_manager.trigger("before_load", this.doctype, this.docname, function() {
		me.script_manager.trigger("onload");
		me.opendocs[me.docname] = true;
		me.render_form();
	})

}

_f.Frm.prototype.runscript = function(scriptname, callingfield, onrefresh) {
	var me = this;
	if(this.docname) {
		// make doc list
		var doclist = wn.model.compress(make_doclist(this.doctype, this.docname));
		// send to run
		if(callingfield)
			$(callingfield.input).set_working();

		return $c('runserverobj', {'docs':doclist, 'method':scriptname }, 
			function(r, rtxt) { 
				// run refresh
				if(onrefresh)
					onrefresh(r,rtxt);

				// fields
				me.refresh_fields();
				
				// enable button
				if(callingfield)
					$(callingfield.input).done_working();
			}
		);
	}
}

_f.Frm.prototype.copy_doc = function(onload, from_amend) {
	if(!this.perm[0][CREATE]) {
		msgprint('You are not allowed to create '+this.meta.name);
		return;
	}
	
	var dn = this.docname;
	// copy parent
	var newdoc = wn.model.copy_doc(this.doctype, dn, from_amend);
	
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
		me.refresh();
	}

	if(!me.doc.__islocal) { 
		wn.model.remove_from_locals(me.doctype, me.docname);
		wn.model.with_doc(me.doctype, me.docname, function() {
			me.refresh();
		})
	}
}

var validated;
_f.Frm.prototype.save = function(save_action, callback, btn, on_error) {
	$(document.activeElement).blur();
	var me = this;
	
	if((!this.meta.in_dialog || this.in_form) && !this.meta.istable)
		scroll(0, 0);
	
	// validate
	if(save_action!="Cancel") {
		validated = true;
		this.script_manager.trigger("validate");
		if(!validated) {
			if(on_error) 
				on_error();
			return;
		}
	}

	var doclist = new wn.model.DocList(this.doctype, this.docname);

	doclist.save(save_action || "Save", function(r) {
		if(!r.exc) {
			me.refresh();
		} else {
			if(on_error)
				on_error();
		}
		callback && callback(r);
		
		if(wn._from_link) {
			if(me.doctype===wn._from_link.df.options) {
				wn._from_link.parse_validate_and_set_in_model(me.docname);
				wn.set_route("Form", wn._from_link.frm.doctype, wn._from_link.frm.docname);
				setTimeout(function() { scroll(0, wn._from_link_scrollY); }, 100);
			}
			wn._from_link = null;
		}
	}, btn);
}


_f.Frm.prototype.savesubmit = function(btn, on_error) {
	var me = this;
	wn.confirm("Permanently Submit "+this.docname+"?", function() {
		validated = true;
		me.script_manager.trigger("before_submit");
		if(!validated) {
			if(on_error) 
				on_error();
			return;
		}

		me.save('Submit', function(r) {
			if(!r.exc) {
				me.script_manager.trigger("on_submit");
			}
		}, btn, on_error);
	});
}

_f.Frm.prototype.savecancel = function(btn, on_error) {
	var me = this;
	wn.confirm("Permanently Cancel "+this.docname+"?", function() {
		validated = true;
		me.script_manager.trigger("before_cancel");
		if(!validated) {
			if(on_error) 
				on_error();
			return;
		}
		
		var doclist = new wn.model.DocList(me.doctype, me.docname);
		doclist.cancel(function(r) {
			if(!r.exc) {
				me.refresh();
				me.script_manager.trigger("after_cancel");
			}
		}, btn, on_error);
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
	this.save_disabled = true;
	this.appframe.set_title_right("", null);
}

_f.Frm.prototype.save_or_update = function() {
	if(this.save_disabled) return;
	
	if(this.doc.docstatus===0) {
		this.save();
	} else if(this.doc.docstatus===1 && this.doc.__unsaved) {
		this.save("Update");
	}
}

_f.get_value = function(dt, dn, fn) {
	if(locals[dt] && locals[dt][dn]) 
		return locals[dt][dn][fn];
}

_f.Frm.prototype.dirty = function() {
	this.doc.__unsaved = 1;
	$(this.wrapper).trigger('dirty')
}

_f.Frm.prototype.get_docinfo = function() {
	return wn.model.docinfo[this.doctype][this.docname];
}

_f.Frm.prototype.get_perm = function(permlevel, access_type) {
	return this.perm[permlevel] ? this.perm[permlevel][access_type] : null;
}


_f.Frm.prototype.set_intro = function(txt) {
	wn.utils.set_intro(this, this.body, txt);
}

_f.Frm.prototype.set_footnote = function(txt) {
	wn.utils.set_footnote(this, this.body, txt);
}


_f.Frm.prototype.add_custom_button = function(label, fn, icon) {
	return this.appframe.add_primary_action(label, fn, icon || "icon-arrow-right");
}
_f.Frm.prototype.clear_custom_buttons = function() {
	this.toolbar.refresh()
}

_f.Frm.prototype.add_fetch = function(link_field, src_field, tar_field) {
	if(!this.fetch_dict[link_field]) {
		this.fetch_dict[link_field] = {'columns':[], 'fields':[]}
	}
	this.fetch_dict[link_field].columns.push(src_field);
	this.fetch_dict[link_field].fields.push(tar_field);
}

_f.Frm.prototype.set_print_heading = function(txt) {
	this.pformat[cur_frm.docname] = txt;
}
