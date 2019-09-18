// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide("frappe.global_tags");

frappe.global_tags.GlobalTagsDialog = class GlobalTags {
	constructor(opts) {
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
		this.dialog = new frappe.ui.Dialog({
			hide_on_page_refresh: true,
			title: __("Tags")
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

frappe.global_tags.utils = {
	get_tags: function(txt) {
		txt = txt.slice(1);
		let out = [];

		frappe.call({
			method: "frappe.utils.global_tags.get_tags_list_for_awesomebar",
			callback: function(r) {
				if (r && r.message) {
					let tags = r.message;
					tags.forEach(tag => {
						let level = frappe.search.utils.fuzzy_search(txt, tag);
						if(level) {
							out.push({
								type: "Tag",
								label: __("#{0}", [frappe.search.utils.bolden_match_part(__(tag), txt)]),
								value: __("#{0}", [__(tag)]),
								index: 1 + level,
								match: tag,
								onclick: function() {
									new frappe.global_tags.GlobalTagsDialog({"tag": txt})
								}
							});
						}
					});
				}
				return out;
			}
		});
	},
}