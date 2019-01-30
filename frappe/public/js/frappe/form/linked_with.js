// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui.form");

frappe.ui.form.LinkedWith = class LinkedWith {

	constructor(opts) {
		$.extend(this, opts);
	}

	show() {
		if(!this.dialog)
			this.make_dialog();

		$(this.dialog.body).html(
			`<div class="text-muted text-center" style="padding: 30px 0px">
				${__("Loading")}...
			</div>`);

		this.dialog.show();
	}

	make_dialog() {

		this.dialog = new frappe.ui.Dialog({
			hide_on_page_refresh: true,
			title: __("Linked With")
		});

		this.dialog.on_page_show = () => {
			// execute ajax calls sequentially
			// 1. get linked doctypes
			// 2. load all doctypes
			// 3. load linked docs
			this.get_linked_doctypes()
				.then(() => this.load_doctypes())
				.then(() => this.links_not_permitted_or_missing())
				.then(() => this.get_linked_docs())
				.then(() => this.make_html());
		};
	}

	make_html() {
		const linked_docs = this.frm.__linked_docs;

		let html = '';

		const linked_doctypes = Object.keys(linked_docs);

		if (linked_doctypes.length === 0) {
			html = __("Not Linked to any record");
		} else {
			html = linked_doctypes.map(doctype => {
				const docs = linked_docs[doctype];
				return `
					<div class="list-item-table margin-bottom">
						${this.make_doc_head(doctype)}
						${docs.map(doc => this.make_doc_row(doc, doctype)).join('')}
					</div>
				`;
			}).join('');
		}

		$(this.dialog.body).html(html);
	}

	load_doctypes() {
		const already_loaded = Object.keys(locals.DocType);
		let doctypes_to_load = [];

		if (this.frm.__linked_doctypes) {
			doctypes_to_load =
				Object.keys(this.frm.__linked_doctypes)
					.filter(doctype => !already_loaded.includes(doctype));
		}

		// load all doctypes asynchronously using with_doctype
		const promises = doctypes_to_load.map(dt => {
			return frappe.model.with_doctype(dt, () => {
				if(frappe.listview_settings[dt]) {
					// add additional fields to __linked_doctypes
					this.frm.__linked_doctypes[dt].add_fields =
						frappe.listview_settings[dt].add_fields;
				}
			});
		});

		return Promise.all(promises);
	}

	links_not_permitted_or_missing() {
		let links = null;

		if (this.frm.__linked_doctypes) {
			links =
				Object.keys(this.frm.__linked_doctypes)
					.filter(frappe.model.can_get_report);
		}

		let flag;
		if(!links) {
			$(this.dialog.body).html(`${this.frm.__linked_doctypes
				? __("Not enough permission to see links")
				: __("Not Linked to any record")}`);
			flag = true;
		}
		flag = false;

		// reject Promise if not_permitted or missing
		return new Promise(
			(resolve, reject) => flag ? reject() : resolve()
		);
	}

	get_linked_doctypes() {
		return new Promise((resolve) => {
			if (this.frm.__linked_doctypes) {
				resolve();
			}

			frappe.call({
				method: "frappe.desk.form.linked_with.get_linked_doctypes",
				args: {
					doctype: this.frm.doctype
				},
				callback: (r) => {
					this.frm.__linked_doctypes = r.message;
					resolve();
				}
			});
		});
	}

	get_linked_docs() {
		return frappe.call({
			method: "frappe.desk.form.linked_with.get_linked_docs",
			args: {
				doctype: this.frm.doctype,
				name: this.frm.docname,
				linkinfo: this.frm.__linked_doctypes,
				for_doctype: this.for_doctype
			},
			callback: (r) => {
				this.frm.__linked_docs = r.message || {};
			}
		});
	}

	make_doc_head(heading) {
		return `
			<header class="level list-row list-row-head text-muted small">
				<div>${__(heading)}</div>
			</header>
		`;
	}

	make_doc_row(doc, doctype) {
		return `<div class="list-row-container">
			<div class="level list-row small">
				<div class="level-left bold">
					<a href="#Form/${doctype}/${doc.name}">${doc.name}</a>
				</div>
			</div>
		</div>`;
	}
};
