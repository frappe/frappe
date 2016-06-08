// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.document_flow');

frappe.ui.form.DocumentFlow = Class.extend({
	init: function(opts) {
		$.extend(this, opts);

		this.module = frappe.get_meta(this.frm.doctype).module
		if (!frappe.document_flow[this.module]) {
			return;
		}
		this.doctypes = frappe.document_flow[this.module][this.frm.doctype];
		if (!this.doctypes) {
			return;
		}

		this.wrapper = $('<div class="document-flow-wrapper hidden"></div>').prependTo(this.frm.layout.wrapper);
	},

	refresh: function() {
		if(this.doctypes) {
			this.reset();
			this.render();
		}
	},

	reset: function() {
		this.wrapper.empty().addClass('hidden');
		this.linked_with = {};
	},

	render: function() {
		var me = this;

		$(frappe.render_template('form_document_flow', {
			frm: this.frm,
			doctypes: this.doctypes,
		})).appendTo(this.wrapper.removeClass('hidden'));

		this.wrapper.on('click', '.document-flow-link', function() {
			var doctype = $(this).attr("data-doctype");
			if (me.frm.doctype != doctype) {
				me.get_linked_docs(doctype);
				return false;
			}
		});
	},

	get_linked_docs: function(for_doctype) {
		if(!this.linked_with[for_doctype]) {
			this.linked_with[for_doctype] = new frappe.ui.form.LinkedWith({
				frm: this.frm,
				for_doctype: for_doctype
			});
		}

		this.linked_with[for_doctype].show();
	}
});
