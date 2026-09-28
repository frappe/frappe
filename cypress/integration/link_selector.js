import doctype_with_child_table from "../fixtures/doctype_with_child_table";
import child_table_doctype from "../fixtures/child_table_doctype";
import child_table_doctype_1 from "../fixtures/child_table_doctype_1";

context("Link Selector", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.insert_doc("DocType", child_table_doctype, true);
		cy.insert_doc("DocType", child_table_doctype_1, true);
		return cy.insert_doc("DocType", doctype_with_child_table, true);
	});

	it("passes the form to a grid field's get_query function", () => {
		cy.new_form(doctype_with_child_table.name);
		cy.window().then((win) => {
			const frm = win.cur_frm;
			let query_args = null;
			frm.set_query("title", "child_table", (doc, cdt, cdn, form) => {
				query_args = { doc, cdt, form };
				return {};
			});

			new win.frappe.ui.form.LinkSelector({
				doctype: "User",
				fieldname: "title",
				target: frm.fields_dict.child_table.grid,
				txt: "",
			});

			cy.wrap(null).should(() => {
				expect(query_args).to.not.equal(null);
				expect(query_args.doc).to.equal(frm.doc);
				expect(query_args.cdt).to.equal("Child Table Doctype");
				expect(query_args.form).to.equal(frm);
			});
		});
	});
});
