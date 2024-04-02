frappe.provide("frappe.ui");

frappe.ui.DiffView = class DiffView {
	constructor(doctype, fieldname, docname) {
		this.dialog = null;
		this.handler = null;
		this.doctype = doctype;
		this.fieldname = fieldname;
		this.docname = docname;

		this.dialog = this.make_dialog();
		this.set_empty_state();
		this.dialog.show();
	}

	make_dialog() {
		const get_query = () => ({
			query: "frappe.utils.diff.version_query",
			filters: {
				docname: this.docname,
				ref_doctype: this.doctype,
				fieldname: this.fieldname,
				page_len: 100,
			},
		});
		const onchange = () => this.compute_diff();
		return new frappe.ui.Dialog({
			title: __("Compare Versions"),
			fields: [
				{
					label: __("From version"),
					fieldtype: "Link",
					fieldname: "from_version",
					options: "Version",
					reqd: 1,
					get_query,
					onchange,
				},
				{
					fieldtype: "Column Break",
					fieldname: "cb",
				},
				{
					label: __("To version"),
					fieldtype: "Link",
					fieldname: "to_version",
					options: "Version",
					reqd: 1,
					get_query,
					onchange,
				},
				{
					fieldtype: "Section Break",
					fieldname: "sb",
				},
				{
					label: __("Diff"),
					fieldtype: "HTML",
					fieldname: "diff",
				},
			],
			size: "extra-large",
		});
	}

	compute_diff() {
		const from_version = this.dialog.get_value("from_version");
		const to_version = this.dialog.get_value("to_version");
		const fieldname = this.fieldname;

		if (from_version && to_version) {
			frappe
				.xcall("frappe.utils.diff.get_version_diff", {
					from_version,
					to_version,
					fieldname,
				})
				.then((data) => {
					this.dialog.set_value("diff", this.prettify_diff(data));
				});
		} else {
			this.set_empty_state();
		}
	}

	prettify_diff(diff) {
		let html = ``;

		diff.forEach((line) => {
			let line_class = "";
			if (line.startsWith("+")) {
				line_class = "insert";
			} else if (line.startsWith("-")) {
				line_class = "delete";
			}
			html += `<div class="${line_class} text-wrap">${line}</div>`;
		});
		return `<div class='diffview'>${html}</div>`;
	}

	set_empty_state() {
		this.dialog.set_value("diff", __("Select two versions to view the diff."));
	}
};
