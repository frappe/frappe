frappe.provide('frappe.ui.form');

frappe.ui.form.make_quick_entry = (doctype, after_insert, init_callback) => {
	var trimmed_doctype = doctype.replace(/ /g, '');
	var controller_name = "QuickEntryForm";

	if(frappe.ui.form[trimmed_doctype + "QuickEntryForm"]){
		controller_name = trimmed_doctype + "QuickEntryForm";
	}

	frappe.quick_entry = new frappe.ui.form[controller_name](doctype, after_insert, init_callback);
	return frappe.quick_entry.setup();
};

frappe.ui.form.QuickEntryForm = Class.extend({
	init: function(doctype, after_insert, init_callback){
		this.doctype = doctype;
		this.after_insert = after_insert;
		this.init_callback = init_callback;
	},

	setup: function() {
		let me = this;
		return new Promise(resolve => {
			frappe.model.with_doctype(this.doctype, function() {
				me.set_meta_and_mandatory_fields();
				if(me.is_quick_entry()) {
					me.render_dialog();
					resolve(me);
				} else {
					frappe.quick_entry = null;
					frappe.set_route('Form', me.doctype, me.doc.name)
						.then(() => resolve(me));
				}
			});
		});
	},

	set_meta_and_mandatory_fields: function(){
		this.mandatory = $.map(frappe.get_meta(this.doctype).fields,
			function(d) { return (d.reqd || d.bold && !d.read_only) ? d : null; });
		this.meta = frappe.get_meta(this.doctype);
		this.doc = frappe.model.get_new_doc(this.doctype, null, null, true);
	},

	is_quick_entry: function(){
		if(this.meta.quick_entry != 1) {
			return false;
		}

		if (this.too_many_mandatory_fields() || this.has_child_table()
			|| !this.mandatory.length) {
			return false;
		}

		this.validate_for_prompt_autoname();
		return true;
	},

	too_many_mandatory_fields: function(){
		if(this.mandatory.length > 7) {
			// too many fields, show form
			return true;
		}
		return false;
	},

	has_child_table: function(){
		if($.map(this.mandatory, function(d) {
			return d.fieldtype==='Table' ? d : null; }).length) {
			// has mandatory table, quit!
			return true;
		}
		return false;
	},

	validate_for_prompt_autoname: function(){
		if(this.meta.autoname && this.meta.autoname.toLowerCase()==='prompt') {
			this.mandatory = [{fieldname:'__name', label:__('{0} Name', [this.meta.name]),
				reqd: 1, fieldtype:'Data'}].concat(this.mandatory);
		}
	},

	render_dialog: function(){
		var me = this;
		this.dialog = new frappe.ui.Dialog({
			title: __("New {0}", [__(this.doctype)]),
			fields: this.mandatory,
		});
		this.dialog.doc = this.doc;
		// refresh dependencies etc
		this.dialog.refresh();

		this.register_primary_action();
		this.render_edit_in_full_page_link();
		// ctrl+enter to save
		this.dialog.wrapper.keydown(function(e) {
			if((e.ctrlKey || e.metaKey) && e.which==13) {
				if(!frappe.request.ajax_count) {
					// not already working -- double entry
					me.dialog.get_primary_btn().trigger("click");
					e.preventDefault();
					return false;
				}
			}
		});

		this.dialog.onhide = () => frappe.quick_entry = null;
		this.dialog.show();
		this.set_defaults();
		
		if (this.init_callback) {
			this.init_callback(this.dialog);
		}
	},

	register_primary_action: function(){
		var me = this;
		this.dialog.set_primary_action(__('Save'), function() {
			if(me.dialog.working) {
				return;
			}
			var data = me.dialog.get_values();

			if(data) {
				me.dialog.working = true;
				me.insert();
			}
		});
	},

	insert: function() {
		let me = this;
		return new Promise(resolve => {
			me.update_doc();
			frappe.call({
				method: "frappe.client.insert",
				args: {
					doc: me.dialog.doc
				},
				callback: function(r) {
					me.dialog.hide();
					// delete the old doc
					frappe.model.clear_doc(me.dialog.doc.doctype, me.dialog.doc.name);
					me.dialog.doc = r.message;
					if(frappe._from_link) {
						frappe.ui.form.update_calling_link(me.dialog.doc);
					} else {
						if(me.after_insert) {
							me.after_insert(me.dialog.doc);
						} else {
							me.open_from_if_not_list();
						}
					}
				},
				error: function() {
					me.open_doc();
				},
				always: function() {
					me.dialog.working = false;
					resolve(me.dialog.doc);
				},
				freeze: true
			});
		});
	},

	open_from_if_not_list: function() {
		let route = frappe.get_route();
		let doc = this.dialog.doc;
		if(route && !(route[0]==='List' && route[1]===doc.doctype)) {
			frappe.set_route('Form', doc.doctype, doc.name);
		}
	},

	update_doc: function(){
		var me = this;
		var data = this.dialog.get_values(true);
		$.each(data, function(key, value) {
			if(key==='__name') {
				me.dialog.doc.name = value;
			} else {
				if(!is_null(value)) {
					me.dialog.doc[key] = value;
				}
			}
		});
		return this.dialog.doc;
	},

	open_doc: function(){
		this.dialog.hide();
		this.update_doc();
		frappe.set_route('Form', this.doctype, this.doc.name);
	},

	render_edit_in_full_page_link: function(){
		var me = this;
		var $link = $('<div class="text-muted small" style="padding-left: 10px; padding-top: 15px;">' +
			__("Ctrl+enter to save") + ' | <a class="edit-full">' + __("Edit in full page") + '</a></div>').appendTo(this.dialog.body);

		$link.find('.edit-full').on('click', function() {
			// edit in form
			me.open_doc();
		});
	},

	set_defaults: function(){
		var me = this;
		// set defaults
		$.each(this.dialog.fields_dict, function(fieldname, field) {
			field.doctype = me.doc.doctype;
			field.docname = me.doc.name;

			if(!is_null(me.doc[fieldname])) {
				field.set_input(me.doc[fieldname]);
			}
		});
	}
});
