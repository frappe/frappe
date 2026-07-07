context("Grid", () => {
	beforeEach(() => {
		cy.login();
		cy.visit("/app/website");
	});
	before(() => {
		cy.login();
		cy.visit("/app/website");
		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.call(
					"frappe.tests.ui_test_helpers.create_contact_phone_nos_records"
				);
			});
	});
	it("update docfield property using update_docfield_property", () => {
		cy.visit("/app/contact/Test Contact");
		cy.window()
			.its("cur_frm")
			.then((frm) => {
				cy.get('.frappe-control[data-fieldname="phone_nos"]').as("table");
				let field = frm.get_field("phone_nos");
				field.grid.update_docfield_property("is_primary_phone", "hidden", true);

				cy.get("@table").find('[data-idx="1"] .btn-open-row').click();
				cy.get(".grid-row-open").as("table-form");
				cy.get("@table-form")
					.find('.frappe-control[data-fieldname="is_primary_phone"]')
					.should("be.hidden");
				cy.get("@table-form").find(".grid-footer-toolbar").click();

				cy.get("@table").find('[data-idx="2"] .btn-open-row').click();
				cy.get(".grid-row-open").as("table-form");
				cy.get("@table-form")
					.find('.frappe-control[data-fieldname="is_primary_phone"]')
					.should("be.hidden");
				cy.get("@table-form").find(".grid-footer-toolbar").click();
			});
	});
	it("update docfield property using toggle_display", () => {
		cy.visit("/app/contact/Test Contact");
		cy.window()
			.its("cur_frm")
			.then((frm) => {
				cy.get('.frappe-control[data-fieldname="phone_nos"]').as("table");
				let field = frm.get_field("phone_nos");
				field.grid.toggle_display("is_primary_mobile_no", false);

				cy.get("@table").find('[data-idx="1"] .btn-open-row').click();
				cy.get(".grid-row-open").as("table-form");
				cy.get("@table-form")
					.find('.frappe-control[data-fieldname="is_primary_mobile_no"]')
					.should("be.hidden");
				cy.get("@table-form").find(".grid-footer-toolbar").click();

				cy.get("@table").find('[data-idx="2"] .btn-open-row').click();
				cy.get(".grid-row-open").as("table-form");
				cy.get("@table-form")
					.find('.frappe-control[data-fieldname="is_primary_mobile_no"]')
					.should("be.hidden");
				cy.get("@table-form").find(".grid-footer-toolbar").click();
			});
	});
	it("update docfield property using toggle_enable", () => {
		cy.visit("/app/contact/Test Contact");
		cy.window()
			.its("cur_frm")
			.then((frm) => {
				cy.get('.frappe-control[data-fieldname="phone_nos"]').as("table");
				let field = frm.get_field("phone_nos");
				field.grid.toggle_enable("phone", false);

				cy.get("@table").find('[data-idx="1"] .btn-open-row').click();
				cy.get(".grid-row-open").as("table-form");
				cy.get("@table-form")
					.find('.frappe-control[data-fieldname="phone"] .control-value')
					.should("have.class", "like-disabled-input");
				cy.get("@table-form").find(".grid-footer-toolbar").click();

				cy.get("@table").find('[data-idx="2"] .btn-open-row').click();
				cy.get(".grid-row-open").as("table-form");
				cy.get("@table-form")
					.find('.frappe-control[data-fieldname="phone"] .control-value')
					.should("have.class", "like-disabled-input");
				cy.get("@table-form").find(".grid-footer-toolbar").click();
			});
	});
	it("update docfield property using toggle_reqd", () => {
		cy.visit("/app/contact/Test Contact");
		cy.window()
			.its("cur_frm")
			.then((frm) => {
				cy.get('.frappe-control[data-fieldname="phone_nos"]').as("table");
				let field = frm.get_field("phone_nos");
				field.grid.toggle_reqd("phone", false);

				cy.get("@table").find('[data-idx="1"] .btn-open-row').click();
				cy.get(".grid-row-open").as("table-form");
				cy.get_field("phone").as("phone-field");
				cy.get("@phone-field").focus().clear().wait(500).blur();
				cy.get("@phone-field").should("not.have.class", "has-error");
				cy.get("@table-form").find(".grid-footer-toolbar").click();

				cy.get("@table").find('[data-idx="2"] .btn-open-row').click();
				cy.get(".grid-row-open").as("table-form");
				cy.get_field("phone").as("phone-field");
				cy.get("@phone-field").focus().clear().wait(500).blur();
				cy.get("@phone-field").should("not.have.class", "has-error");
				cy.get("@table-form").find(".grid-footer-toolbar").click();
			});
	});
	it("keeps child table in sync after backend removes a reordered row", () => {
		let original_order;
		cy.visit("/app/log-settings");
		cy.window()
			.its("cur_frm")
			.then((frm) => {
				original_order = frm.doc.logs_to_clear.map((row) => row.ref_doctype);
				// add an unsupported doctype and move it off the last position
				frm.add_child("logs_to_clear", { ref_doctype: "User", days: 30 });
				const rows = frm.doc.logs_to_clear;
				rows.splice(1, 0, rows.pop());
				rows.forEach((row, i) => (row.idx = i + 1));
				frm.refresh_field("logs_to_clear");
			});
		cy.save();
		cy.get(".modal-dialog").contains("not supported").should("be.visible");
		cy.get(".modal-header .btn-modal-close").click({ force: true });
		cy.window()
			.its("cur_frm")
			.then((frm) => {
				const rows = frm.doc.logs_to_clear;
				// the unsupported row is gone and no empty/ghost rows remain
				expect(rows.find((row) => row.ref_doctype === "User")).to.be.undefined;
				expect(rows.every((row) => row.ref_doctype)).to.be.true;
				cy.get(
					'.frappe-control[data-fieldname="logs_to_clear"] .grid-body .grid-row'
				).should("have.length", rows.length);
				// restore the original order so the global singleton is left untouched
				rows.sort(
					(a, b) =>
						original_order.indexOf(a.ref_doctype) -
						original_order.indexOf(b.ref_doctype)
				);
				rows.forEach((row, i) => (row.idx = i + 1));
				frm.refresh_field("logs_to_clear");
			});
		cy.save();
	});
});
