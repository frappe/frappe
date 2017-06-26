frappe.provide('frappe.ui.form');

frappe.ui.form.make_quick_entry = (doctype) => {
	return new Promise((resolve) => {
		var trimmed_doctype = doctype.replace(/ /g, '');
		var controller_name = "QuickEntryForm";

		if(frappe.ui.form[trimmed_doctype + "QuickEntryForm"]){
			controller_name = trimmed_doctype + "QuickEntryForm";
		}

		frappe.quick_entry = new frappe.ui.form[controller_name](doctype)
		frappe.quick_entry.setup()
			.then((frm) => { resolve(frm); });
	});
}

frappe.ui.form.QuickEntryForm = Class.extend({
	init: function(doctype, after_insert){
		this.doctype = doctype;
		this.after_insert = after_insert;
	},

	setup: function(resolve) {
		let me = this;
		return new Promise((resolve) => {
			frappe.model.with_doctype(this.doctype, function() {
				me.set_meta_and_mandatory_fields();
				var validate_flag = me.validate_quick_entry();
				if(!validate_flag){
					me.render_dialog();
				}
				resolve(me);
			});
		});
	},

	set_meta_and_mandatory_fields: function(){
		this.mandatory = $.map(frappe.get_meta(this.doctype).fields,
			function(d) { return (d.reqd || d.bold && !d.read_only) ? d : null; });
		this.meta = frappe.get_meta(this.doctype);
		this.doc = frappe.model.get_new_doc(this.doctype, null, null, true);
	},

	validate_quick_entry: function(){
		if(this.meta.quick_entry != 1) {
			frappe.set_route('Form', this.doctype, this.doc.name);
			return true;
		}
		var mandatory_flag = this.validate_mandatory_length();
		var child_table_flag = this.validate_for_child_table();

		if (mandatory_flag || child_table_flag){
			return true;
		}
		this.validate_for_prompt_autoname();
	},

	validate_mandatory_length: function(){
		if(this.mandatory.length > 7) {
			// too many fields, show form
			frappe.set_route('Form', this.doctype, this.doc.name);
			return true;
		}
	},

	validate_for_child_table: function(){
		if($.map(this.mandatory, function(d) { return d.fieldtype==='Table' ? d : null; }).length) {
			// has mandatory table, quit!
			frappe.set_route('Form', this.doctype, this.doc.name);
			return true;
		}
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

		this.dialog.show();
		this.set_defaults();
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
				me.insert(values);
			}
		});
	},

	insert: function(values){
		let me = this;
		return new Promise((resolve) => {
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
						frappe.ui.form.update_calling_link(me.dialog.doc.name);
					} else {
						if(me.after_insert) {
							me.after_insert(me.dialig.doc);
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
			frappe.set_route('Form', doc.doctype, doc.name)
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
