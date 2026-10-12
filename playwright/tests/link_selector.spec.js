import { test, expect } from "../support";
import doctype_with_child_table from "../fixtures/doctype_with_child_table";
import child_table_doctype from "../fixtures/child_table_doctype";
import child_table_doctype_1 from "../fixtures/child_table_doctype_1";

test.describe("Link Selector", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", child_table_doctype, true);
		await admin.insert_doc("DocType", child_table_doctype_1, true);
		await admin.insert_doc("DocType", doctype_with_child_table, true);
	});

	test("passes the form to a grid field's get_query function", async ({ page, desk }) => {
		await desk.new_form(doctype_with_child_table.name);
		await page.evaluate(() => {
			const frm = cur_frm;
			window.link_selector_query_args = null;
			frm.set_query("title", "child_table", (doc, cdt, cdn, form) => {
				window.link_selector_query_args = { doc, cdt, form };
				return {};
			});

			new frappe.ui.form.LinkSelector({
				doctype: "User",
				fieldname: "title",
				target: frm.fields_dict.child_table.grid,
				txt: "",
			});
		});

		await expect
			.poll(() =>
				page.evaluate(() => {
					const query_args = window.link_selector_query_args;
					return (
						query_args && {
							is_form_doc: query_args.doc === cur_frm.doc,
							cdt: query_args.cdt,
							is_form: query_args.form === cur_frm,
						}
					);
				})
			)
			.toEqual({ is_form_doc: true, cdt: "Child Table Doctype", is_form: true });
	});
});
