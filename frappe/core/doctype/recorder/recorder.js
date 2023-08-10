// Copyright (c) 2023, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Recorder Query", "form_render", function (frm, cdt, cdn) {
	let row = frappe.get_doc(cdt, cdn);
	let stack = JSON.parse(row.stack);
	render_html_field(stack, "stack_html", "Stack Trace");

	let explain_result = JSON.parse(row.explain_result);
	render_html_field(explain_result, "sql_explain_html", "SQL Explain");

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
		html +=
			"<div class='control-value like-disabled-input for-description' style='overflow:auto; padding:0px'>";
		html += "<table class='table table-striped' style='margin:0px'><thead><tr>";
		Object.keys(table_content[0]).forEach((key) => {
			html += "<th>" + key + "</th>";
		});
		html += "</tr></thead><tbody>";

		for (let row in table_content) {
			html += "<tr>";
			Object.values(table_content[row]).forEach((value) => {
				html += "<td>" + value + "</td>";
			});
			html += "</tr>";
		}
		html += "</tbody></table></div>";
		return html;
	}
});
