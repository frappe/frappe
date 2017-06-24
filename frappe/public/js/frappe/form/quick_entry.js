frappe.provide('frappe.ui.form');

frappe.ui.form.QuickEntryForm = Class.extend({
	init: function(doctype, success_function){
		this.doctype = doctype;
		this.success_function = success_function;
		this.setup();
	},

	setup: function(){
		var me = this;
		frappe.model.with_doctype(this.doctype, function() {
			me.set_meta_and_mandatory_fields();
			var validate_flag = me.validate_quick_entry();
			if(!validate_flag){
				me.render_dialog();
			}
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
			if(me.dialog.working) return;
			var data = me.dialog.get_values();

			if(data) {
				me.dialog.working = true;
				var values = me.update_doc();
				me.insert_document(values);
			}
		});
	},

	insert_document: function(values){
		var me = this;
		frappe.call({
			method: "frappe.client.insert",
			args: {
				doc: values
			},
			callback: function(r) {
				me.dialog.hide();
				// delete the old doc
				frappe.model.clear_doc(me.dialog.doc.doctype, me.dialog.doc.name);
				var doc = r.message;
				if(me.success_function) {
					me.success_function(doc);
				}
				frappe.ui.form.update_calling_link(doc.name);
			},
			error: function() {
				me.open_doc();
			},
			always: function() {
				me.dialog.working = false;
			},
			freeze: true
		});
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
