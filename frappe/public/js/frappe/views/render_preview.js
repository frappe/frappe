// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide("frappe.views");

frappe.views.RenderPreviewer = class RenderPreviewer {
	constructor(opts) {
		$.extend(this, opts);
		this.make();
	}

	make() {
		let me = this;

		me.set_fields();
		let fields = me.header_fields;
		fields.push(...me.body_fields);

		me.dialog = new frappe.ui.Dialog({
			title: __("Preview on {0}", [__(me.doctype)]),
			no_submit_on_enter: true,
			fields: fields,
			minimizable: true,
			size: "large",
		});

		me.prepare();
		me.dialog.show();
	}

	set_fields() {
		let me = this;
		me.header_fields = [
			{
				label: __("Reference Doctype"),
				fieldtype: "Link",
				fieldname: "doctype",
				reqd: 1,
				read_only: 1,
				hidden: 1,
			},
			{
				label: __("Document"),
				fieldtype: "Dynamic Link",
				fieldname: "preview_document",
				options: "doctype",
				reqd: 1,
				onchange: () => me.render_previews(),
			},
		];
		me.body_fields = [{ fieldtype: "Section Break" }];

		me.preview_fields.forEach((spec) => {
			let field = {
				label: spec.label,
				fieldtype: spec.fieldtype,
				fieldname: spec.method,
				read_only: 1,
			};
			if (spec.method === "preview_meets_condition") {
				me.header_fields.push({ fieldtype: "Column Break" });
				me.header_fields.push(field);
			} else {
				me.body_fields.push(field);
			}
		});
	}

	prepare() {
		let me = this;
		me.dialog.set_values({
			doctype: me.doctype,
		});
	}
	async render_previews() {
		let me = this;
		let preview_document = me.dialog.get_value("preview_document");
		if (preview_document) {
			let promises = [];
			me.preview_fields.forEach((spec) => {
				let fieldname = spec.method;
				promises.push(
					frappe
						.xcall("run_doc_method", {
							dt: me.doc.doctype,
							dn: me.doc.name,
							method: spec.method,
							arg: preview_document,
						})
						.then((message) => me.dialog.set_value(fieldname, message))
				);
			});
			await Promise.all(promises);
		} else {
			me.preview_fields.forEach((spec) => {
				let fieldname = spec.method;
				me.dialog.set_value(fieldname, null);
			});
		}
	}
};
