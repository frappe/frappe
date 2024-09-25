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
		frm.fields_dict.sql_queries.grid.grid_pagination.page_length = 500;
		refresh_field("sql_queries");
		frm.trigger("format_grid");
		frm.add_custom_button(__("Suggest Optimizations"), () => {
			frappe.xcall("frappe.core.doctype.recorder.recorder.optimize", {
				recorder_id: frm.doc.name,
			});
		});

		frappe.realtime.on("recorder-analysis-complete", () => {
			frm.reload_doc();
			setTimeout(() => frm.scroll_to_field("suggested_indexes"), 1500);
		});

		let index_grid = frm.fields_dict.suggested_indexes.grid;
		index_grid.wrapper.find(".grid-footer").toggle(true);
		index_grid.toggle_checkboxes(true);
		index_grid.df.cannot_delete_rows = true;
		index_grid.add_custom_button(__("Add Indexes"), function () {
			let indexes_to_add = index_grid.get_selected_children().map((row) => {
				return {
					column: row.column,
					table: row.table,
				};
			});
			if (!indexes_to_add.length) {
				frappe.toast(__("You need to select indexes you want to add first."));
				return;
			}
			frappe.xcall("frappe.core.doctype.recorder.recorder.add_indexes", {
				indexes: indexes_to_add,
			});
		});
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
				frm.trigger("format_grid");
			});
		});
	},

	/// Format duration and copy cells
	format_grid(frm) {
		const max_duration = Math.max(20, ...frm.doc.sql_queries.map((d) => d.duration));

		const heatmap = (table, field, max) => {
			frm.fields_dict[table].grid.grid_rows.forEach((row) => {
				const percent = Math.round((row.doc[field] / max) * 100);
				$(row.columns[field]).css({
					"background-color": `color-mix(in srgb, var(--bg-red) ${percent}%, var(--bg-color))`,
				});
			});
		};
		heatmap("sql_queries", "duration", max_duration);
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
