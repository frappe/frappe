// Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See LICENSE

frappe.ui.form.LinkedWith = class LinkedWith {
	constructor(opts) {
		$.extend(this, opts);
	}

	show() {
		if (!this.dialog) this.make_dialog();

		$(this.dialog.body).html(
			`<div class="text-muted text-center" style="padding: 30px 0px">
				${__("Loading")}...
			</div>`
		);

		this.dialog.show();
	}

	make_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Links"),
			minimizable: true,
		});

		this.dialog.on_page_show = () => {
			frappe
				.xcall("frappe.desk.form.linked_with.get", {
					doctype: this.frm.doctype,
					docname: this.frm.docname,
				})
				.then((r) => {
					this.frm.__linked_docs = r;
				})
				.then(() => this.make_html());
		};
	}

	make_html() {
		let html = "";
		const linked_docs = this.frm.__linked_docs;
		const linked_doctypes = Object.keys(linked_docs).filter((dt) => {
			const entry = linked_docs[dt];
			return (entry.docs && entry.docs.length) || entry.hidden_count > 0;
		});

		if (linked_doctypes.length === 0) {
			html = __("Not Linked to any record");
		} else {
			html = `
					<div class="margin-bottom">
					${__("Following documents are linked with {0}", [
						frappe.utils
							.get_form_link(this.frm.doctype, this.frm.docname, true)
							.bold(),
					])}
					</div>
					${linked_doctypes
						.map((doctype) => {
							const { docs, hidden_count } = linked_docs[doctype];
							let rows = (docs || [])
								.map((doc) => this.make_doc_row(doc, doctype))
								.join("");
							if (hidden_count > 0) {
								rows += this.make_hidden_count_row(hidden_count);
							}
							return `
						<div class="list-item-table margin-bottom">
							${this.make_doc_head(doctype)}
							${rows}
						</div>
					`;
						})
						.join("")}
					`;
		}

		$(this.dialog.body).html(html);
	}

	make_doc_head(heading) {
		return `
			<header class="level list-row list-row-head text-muted small">
				<div>${__(heading)}</div>
			</header>
		`;
	}

	make_hidden_count_row(count) {
		return `<div class="list-row-container">
			<div class="level list-row small text-muted">
				<div class="level-left">
					${count == 1 ? __("{0} restricted document", [count]) : __("{0} restricted documents", [count])}
				</div>
			</div>
		</div>`;
	}

	make_doc_row(doc, doctype) {
		return `<div class="list-row-container">
			<div class="level list-row small">
				<div class="level-left bold">
					<a href="/desk/${frappe.router.slug(doctype)}/${doc.name}">${doc.name}</a>
				</div>
			</div>
		</div>`;
	}
};
