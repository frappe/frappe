// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide("frappe.global_tags");

frappe.global_tags.GlobalTagsDialog = class GlobalTags {
	constructor(opts) {
		console.log(opts);
		$.extend(this, opts);
		this.show();
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
		let title = __("Tag {0}", [`${__(this.tag)}`]);

		this.dialog = new frappe.ui.Dialog({
			hide_on_page_refresh: true,
			title: title
		});

		this.dialog.on_page_show = () => {
			this.get_documents_for_tag()
				.then(() => this.make_html());
		};
	}

	make_html() {
		const results = this.results;
		let html = '';

		const linked_doctypes = Object.keys(results);

		if (linked_doctypes.length === 0) {
			html = __("Not Linked to any record");
		} else {
			html = linked_doctypes.map(doctype => {
				const docs = results[doctype];
				return `
					<div class="list-item-table margin-bottom">
						${this.make_doc_head(doctype)}
						${docs.map(doc => this.make_doc_row(doc.name, doctype, doc.title)).join('')}
					</div>
				`;
			}).join('');
		}

		$(this.dialog.body).html(html);
	}

	get_documents_for_tag() {
		return new Promise((resolve) => {
			frappe.call({
				method: "frappe.utils.global_tags.get_documents_for_tag",
				args: {
					tag: this.tag
				},
				callback: (r) => {
					this.results = r.message;
					resolve();
				}
			});
		});
	}

	make_doc_head(heading) {
		return `
			<header class="level list-row list-row-head text-muted small">
				<div>${__(heading)}</div>
			</header>
		`;
	}

	make_doc_row(docname, doctype, title) {
		return `<div class="list-row-container">
			<div class="level list-row small">
				<div class="level-left bold">
					<a href="#Form/${doctype}/${docname}">${docname}</a>
				</div>
				<div class="level-left">
					<p>${title}</p>
				</div>
			</div>
		</div>`;
	}
};
