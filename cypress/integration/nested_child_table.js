const root_doctype = "Nested Grid Test Parent";
const child_doctype = "Nested Grid Test Child";
const grandchild_doctype = "Nested Grid Test Detail";

context("Nested child table", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.call("frappe.tests.ui_test_helpers.create_child_doctype", {
			name: grandchild_doctype,
			fields: [{ label: "Value", fieldname: "value", fieldtype: "Data", in_list_view: 1 }],
		});
		cy.call("frappe.tests.ui_test_helpers.create_child_doctype", {
			name: child_doctype,
			fields: [
				{ label: "Label", fieldname: "label", fieldtype: "Data", in_list_view: 1 },
				{
					label: "Details",
					fieldname: "details",
					fieldtype: "Table",
					options: grandchild_doctype,
				},
			],
		});
		cy.insert_doc(
			"DocType",
			{
				name: root_doctype,
				module: "Core",
				custom: 1,
				autoname: "field:title",
				fields: [
					{ label: "Title", fieldname: "title", fieldtype: "Data", reqd: 1 },
					{
						label: "Rows",
						fieldname: "rows",
						fieldtype: "Table",
						options: child_doctype,
					},
				],
				permissions: [{ role: "System Manager", read: 1, write: 1, create: 1, delete: 1 }],
			},
			true
		);
	});

	beforeEach(() => {
		cy.login();
	});

	it("adds and removes grandchildren in the expanded row and survives reload", () => {
		const title = `Nested grid ${Date.now()}`;
		cy.new_form(root_doctype);
		cy.fill_field("title", title);
		cy.get('.frappe-control[data-fieldname="rows"]').first().as("rows");
		cy.get("@rows").find(".grid-add-row").first().click();
		cy.get("@rows").find('.grid-row[data-idx="1"] .btn-open-row').first().click();
		cy.get('.grid-row-open .frappe-control[data-fieldname="details"]').first().as("details");
		cy.get("@details").find(".grid-add-row").first().click();
		cy.get("@details").find('.grid-row[data-idx="1"] .btn-open-row').first().click();
		cy.get(".grid-row-open").should("have.length", 2);
		cy.get("@details")
			.find('.grid-row-open .frappe-control[data-fieldname="value"] input')
			.type("nested value")
			.blur();
		cy.save();
		cy.visit(`/desk/nested-grid-test-parent/${encodeURIComponent(title)}`);
		cy.get('.frappe-control[data-fieldname="rows"] .grid-row[data-idx="1"] .btn-open-row')
			.first()
			.click();
		cy.get('.grid-row-open .frappe-control[data-fieldname="details"]').first().as("details");
		cy.get('.grid-row-open .frappe-control[data-fieldname="details"] .grid-row').should(
			"have.length",
			1
		);
		cy.window().its("cur_frm.doc.rows.0.details.0.value").should("eq", "nested value");
		cy.window().then((win) => {
			win.__nested_detail_events = 0;
			win.frappe.ui.form.on(grandchild_doctype, "value", () => {
				win.__nested_detail_events++;
			});
		});
		cy.get("@details").find('.grid-row[data-idx="1"] .btn-open-row').first().click();
		cy.get("@details")
			.find('.grid-row-open .frappe-control[data-fieldname="value"] input')
			.clear()
			.type("edited value")
			.blur();
		cy.window().should((win) => {
			expect(win.cur_frm.is_dirty()).to.equal(true);
			expect(win.__nested_detail_events).to.be.greaterThan(0);
		});
		cy.save();
		cy.visit(`/desk/nested-grid-test-parent/${encodeURIComponent(title)}`);
		cy.window().its("cur_frm.doc.rows.0.details.0.value").should("eq", "edited value");
		cy.get('.frappe-control[data-fieldname="rows"] .grid-row[data-idx="1"] .btn-open-row')
			.first()
			.click();
		cy.window().then(({ cur_frm }) => {
			const nested = cur_frm.doc.rows[0].details[0];
			const grid = cur_frm.fields_dict.rows.grid.get_row(cur_frm.doc.rows[0].name).grid_form
				.layout.fields_dict.details.grid;
			grid.get_row(nested.name).remove();
		});
		cy.save();
		cy.visit(`/desk/nested-grid-test-parent/${encodeURIComponent(title)}`);
		cy.window().its("cur_frm.doc.rows.0.details").should("have.length", 0);
	});

	it("clears grandchild records when all nested rows are deleted", () => {
		const title = `Nested bulk delete ${Date.now()}`;
		cy.insert_doc(root_doctype, {
			title,
			rows: [
				{ details: [{ value: "first" }, { value: "second" }] },
				{ details: [{ value: "keep" }] },
			],
		});
		cy.visit(`/desk/nested-grid-test-parent/${encodeURIComponent(title)}`);
		cy.get('.frappe-control[data-fieldname="rows"] .grid-row[data-idx="1"] .btn-open-row')
			.first()
			.click();
		cy.window().then(({ cur_frm, frappe, locals }) => {
			const [row, other_row] = cur_frm.doc.rows;
			const removed_names = row.details.map((detail) => detail.name);
			const kept_name = other_row.details[0].name;
			const grid = cur_frm.fields_dict.rows.grid.get_row(row.name).grid_form.layout
				.fields_dict.details.grid;

			cy.stub(frappe, "confirm").callsFake((message, confirm) => confirm());
			grid.delete_all_rows();

			expect(row.details).to.have.length(0);
			removed_names.forEach(
				(name) => expect(locals[grandchild_doctype][name]).to.be.undefined
			);
			expect(locals[grandchild_doctype][kept_name]).to.exist;
		});
		cy.save();
		cy.visit(`/desk/nested-grid-test-parent/${encodeURIComponent(title)}`);
		cy.window().should(({ cur_frm }) => {
			expect(cur_frm.doc.rows[0].details).to.have.length(0);
			expect(cur_frm.doc.rows[1].details[0].value).to.equal("keep");
		});
	});

	it("reorders grandchild rows and persists their indexes", () => {
		const title = `Nested reorder ${Date.now()}`;
		cy.insert_doc(root_doctype, {
			title,
			rows: [{ details: [{ value: "first" }, { value: "second" }] }],
		});
		cy.visit(`/desk/nested-grid-test-parent/${encodeURIComponent(title)}`);
		cy.get('.frappe-control[data-fieldname="rows"] .grid-row[data-idx="1"] .btn-open-row')
			.first()
			.click();
		cy.get('.grid-row-open .frappe-control[data-fieldname="details"]').first().as("details");
		cy.get("@details").find(".grid-body .grid-row").should("have.length", 2);
		cy.get("@details")
			.find('.grid-body .grid-row[data-idx="1"] .sortable-handle')
			.drag(
				'.grid-row-open .frappe-control[data-fieldname="details"] .grid-body .grid-row[data-idx="2"]',
				{
					force: true,
				}
			);
		cy.get("@details")
			.find('.grid-body .grid-row[data-idx="1"]')
			.should("contain.text", "second");
		cy.window().should(({ cur_frm }) => {
			expect(cur_frm.doc.rows[0].details.map((row) => [row.value, row.idx])).to.deep.equal([
				["second", 1],
				["first", 2],
			]);
		});
		cy.save();
		cy.visit(`/desk/nested-grid-test-parent/${encodeURIComponent(title)}`);
		cy.get('.frappe-control[data-fieldname="rows"] .grid-row[data-idx="1"] .btn-open-row')
			.first()
			.click();
		cy.get('.grid-row-open .frappe-control[data-fieldname="details"] .grid-row[data-idx="1"]')
			.first()
			.should("contain.text", "second");
		cy.window().should(({ cur_frm }) => {
			expect(cur_frm.doc.rows[0].details.map((row) => [row.value, row.idx])).to.deep.equal([
				["second", 1],
				["first", 2],
			]);
		});
	});

	it("clears child and grandchild records when all parent rows are deleted", () => {
		const title = `Nested parent bulk delete ${Date.now()}`;
		cy.insert_doc(root_doctype, {
			title,
			rows: [{ details: [{ value: "first" }] }, { details: [{ value: "second" }] }],
		});
		cy.visit(`/desk/nested-grid-test-parent/${encodeURIComponent(title)}`);
		cy.get('.frappe-control[data-fieldname="rows"] .grid-body .grid-row[data-idx]').should(
			"have.length",
			2
		);
		cy.window().then(({ cur_frm, frappe, locals }) => {
			const child_names = cur_frm.doc.rows.map((row) => row.name);
			const grandchild_names = cur_frm.doc.rows.flatMap((row) =>
				row.details.map((detail) => detail.name)
			);

			cy.stub(frappe, "confirm").callsFake((message, confirm) => confirm());
			cur_frm.fields_dict.rows.grid.delete_all_rows();

			expect(cur_frm.doc.rows).to.have.length(0);
			child_names.forEach((name) => expect(locals[child_doctype][name]).to.be.undefined);
			grandchild_names.forEach(
				(name) => expect(locals[grandchild_doctype][name]).to.be.undefined
			);
		});
		cy.save();
		cy.visit(`/desk/nested-grid-test-parent/${encodeURIComponent(title)}`);
		cy.window().its("cur_frm.doc.rows").should("have.length", 0);
	});
});
