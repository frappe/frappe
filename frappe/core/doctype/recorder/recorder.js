// Copyright (c) 2023, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Recorder", {
	onload: function (frm) {
		frm.fields_dict.sql_queries.grid.only_sortable();
	},
	refresh: function (frm) {
		frm.disable_save();
		frm._sort_order = {};
		frm.trigger("setup_sort");
	},

	setup_sort: function (frm) {
		const sortable_fields = ["index", "duration", "exact_copies", "normalized_copies"];
		sortable_fields.forEach((field) => {
			const field_header = $(`.col[data-fieldname='${field}']`)[0];
			$(field_header).click(() => {
				let sort_order = frm._sort_order[field] || -1;
				let grid = frm.fields_dict.sql_queries.grid;
				grid.data.sort((a, b) => sort_order * (a[field] - b[field]));
				frm._sort_order[field] = -1 * sort_order; // reverse for next click
				grid.refresh();
				frm.trigger("setup_sort"); // grid creates new elements again, resetup listeners.
			});
		});
	},
});

frappe.ui.form.on("Recorder Query", "form_render", function (frm, cdt, cdn) {
	let row = frappe.get_doc(cdt, cdn);
	let stack = JSON.parse(row.stack);
	render_html_field(stack, "stack_html", __("Stack Trace"));

	let explain_result = JSON.parse(row.explain_result);
	render_html_field(explain_result, "sql_explain_html", __("SQL Explain"));

	function render_html_field(parsed_json, fieldname, label) {
		let html =
			"<div class='clearfix'><label class='control-label'>" + label + "</label></div>";
		if (parsed_json.length == 0) {
			html += "<label class='control-label'>None</label>";
		} else {
			html = create_html_table(parsed_json, html);
		}

		let field_wrapper =
			frm.fields_dict[row.parentfield].grid.grid_rows_by_docname[cdn].grid_form.fields_dict[
				fieldname
			].wrapper;
		$(html).appendTo(field_wrapper);
	}

	function create_html_table(table_content, html) {
		html += `
			<div class='control-value like-disabled-input for-description'
				style='overflow:auto; padding:0px'>
				<table class='table table-striped' style='margin:0px'>
					<thead>
						<tr>
							${Object.keys(table_content[0])
								.map((key) => `<th>${key}<th>`)
								.join("")}
						</tr>
					</thead>
					<tbody>
						${table_content
							.map((content) => {
								return `
									<tr>
										${Object.values(content)
											.map((key) => `<td>${key}<td>`)
											.join("")}
									</tr>
								`;
							})
							.join("")}
					</tbody>
				</table>
			</div>
		`;
		return html;
	}
});
