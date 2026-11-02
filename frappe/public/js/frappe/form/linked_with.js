// Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See LICENSE

frappe.ui.form.LinkedWith = class LinkedWith {
	constructor(opts) {
		$.extend(this, opts);
		this.page_length = 50;
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
			this.docname = this.frm.docname;
			this.get_linked_docs()
				.then((r) => {
					for (const entry of Object.values(r)) {
						entry.has_more = entry.docs.length > this.page_length;
						entry.docs = entry.docs.slice(0, this.page_length);
					}
					this.frm.__linked_docs = r;
				})
				.then(() => this.make_html());
		};

		$(this.dialog.body).on("click", "[data-action='load-more']", (e) => {
			const $button = $(e.currentTarget).prop("disabled", true);
			this.load_more($button.closest("[data-doctype]")).finally(() =>
				$button.prop("disabled", false)
			);
		});
	}

	get_linked_docs(args) {
		return frappe.xcall("frappe.desk.form.linked_with.get", {
			doctype: this.frm.doctype,
			docname: this.docname,
			limit: this.page_length + 1,
			...args,
		});
	}

	load_more($doctype_table) {
		const doctype = $doctype_table.attr("data-doctype");
		const entry = this.frm.__linked_docs[doctype];
		return this.get_linked_docs({ linked_doctype: doctype, offset: entry.docs.length }).then(
			(r) => {
				const docs = r[doctype]?.docs || [];
				entry.has_more = docs.length > this.page_length;
				entry.docs.push(...docs.slice(0, this.page_length));
				$doctype_table.html(this.make_doctype_html(doctype));
			}
		);
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
						.map(
							(doctype) => `
						<div class="list-item-table margin-bottom" data-doctype="${frappe.utils.escape_html(doctype)}">
							${this.make_doctype_html(doctype)}
						</div>
					`
						)
						.join("")}
					`;
		}

		$(this.dialog.body).html(html);
	}

	make_doctype_html(doctype) {
		const { docs, hidden_count, has_more } = this.frm.__linked_docs[doctype];
		let html = this.make_doc_head(doctype);
		html += docs.map((doc) => this.make_doc_row(doc, doctype)).join("");
		if (has_more) {
			html += this.make_load_more_row();
		}
		if (hidden_count > 0) {
			html += this.make_hidden_count_row(hidden_count);
		}
		return html;
	}

	make_doc_head(heading) {
		return `
			<header class="level list-row list-row-head text-muted small">
				<div>${__(heading)}</div>
			</header>
		`;
	}

	make_load_more_row() {
		return `<div class="list-row-container">
			<div class="level list-row">
				${frappe.ui.button.html({ label: __("Load More"), attrs: { "data-action": "load-more" } })}
			</div>
		</div>`;
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
					<a href="/desk/${frappe.router.slug(doctype)}/${frappe.utils.escape_html(
			doc.name
		)}">${frappe.utils.escape_html(doc.name)}</a>
				</div>
			</div>
		</div>`;
	}
};
