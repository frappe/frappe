context("Grid", () => {
	beforeEach(() => {
		cy.login();
		cy.visit("/desk/website");
	});
	before(() => {
		cy.login();
		cy.visit("/desk/website");
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
		cy.visit("/desk/contact/Test Contact");
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
		cy.visit("/desk/contact/Test Contact");
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
		cy.visit("/desk/contact/Test Contact");
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
		cy.visit("/desk/contact/Test Contact");
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

	it("shows edit button only when child table allow_bulk_edit is enabled", () => {
		cy.visit("/desk/contact/Test Contact");
		cy.get('.frappe-control[data-fieldname="phone_nos"]').as("table");

		cy.window()
			.its("cur_frm")
			.then((frm) => {
				const grid = frm.get_field("phone_nos").grid;
				grid.meta.allow_bulk_edit = false;
				grid.refresh_edit_rows_button();
			});

		cy.get("@table").find('.grid-row[data-idx="1"] .grid-row-check').click({ force: true });
		cy.get("@table").find(".grid-edit-rows").should("have.class", "hidden");

		cy.window()
			.its("cur_frm")
			.then((frm) => {
				const grid = frm.get_field("phone_nos").grid;
				grid.meta.allow_bulk_edit = true;
				grid.refresh_edit_rows_button();
			});

		cy.get("@table").find(".grid-edit-rows").should("not.have.class", "hidden");
	});

	it("bulk edit updates only selected child rows", () => {
		const updated_phone = `99999${Date.now().toString().slice(-5)}`;

		cy.visit("/desk/contact/Test Contact");
		cy.get('.frappe-control[data-fieldname="phone_nos"]').as("table");

		cy.window()
			.its("cur_frm")
			.then((frm) => {
				const grid = frm.get_field("phone_nos").grid;
				grid.meta.allow_bulk_edit = true;
				grid.refresh_edit_rows_button();

				expect(frm.doc.phone_nos.length).to.be.greaterThan(1);
				const phone_df = grid.docfields.find((df) => df.fieldname === "phone");
				expect(phone_df).to.exist;
				cy.wrap(phone_df.label).as("phoneFieldLabel");
				cy.wrap(frm.doc.phone_nos[1].phone || "").as("secondRowPhoneBefore");
			});

		cy.get("@table").find('.grid-row[data-idx="1"] .grid-row-check').click({ force: true });
		cy.get("@table").find(".grid-edit-rows").click({ force: true });

		cy.window()
			.its("cur_dialog")
			.then((dialog) => {
				cy.get("@phoneFieldLabel").then((phoneFieldLabel) => {
					return dialog
						.set_value("field", phoneFieldLabel)
						.then(() => dialog.set_value("value", updated_phone))
						.then(() => {
							dialog.get_primary_btn().click();
						});
				});
			});

		cy.window().its("cur_frm.doc.phone_nos.0.phone").should("eq", updated_phone);
		cy.window()
			.its("cur_frm")
			.then((frm) => {
				cy.get("@secondRowPhoneBefore").then((secondRowPhoneBefore) => {
					expect(frm.doc.phone_nos[1].phone || "").to.equal(secondRowPhoneBefore);
				});
			});
	});

	it("hides add-row and add-multiple-rows buttons when rows are selected", () => {
		cy.visit("/desk/contact/Test Contact");
		cy.get('.frappe-control[data-fieldname="phone_nos"]').as("table");

		cy.get("@table").find('.grid-row[data-idx="1"] .grid-row-check').click({ force: true });

		cy.get("@table").find(".grid-add-row").should("have.class", "hidden");
		cy.get("@table").find(".grid-add-multiple-rows").should("have.class", "hidden");

		cy.get("@table").find('.grid-row[data-idx="1"] .grid-row-check').click({ force: true });

		cy.get("@table").find(".grid-add-row").should("not.have.class", "hidden");
	});

	it("keeps selection count unchanged after duplicate_rows", () => {
		cy.visit("/desk/contact/Test Contact");
		cy.get('.frappe-control[data-fieldname="phone_nos"]').as("table");

		cy.get("@table").find('.grid-row[data-idx="1"] .grid-row-check').click({ force: true });
		cy.get("@table").find('.grid-row[data-idx="2"] .grid-row-check').click({ force: true });
		cy.get("@table").find('.grid-row[data-idx="3"] .grid-row-check').click({ force: true });
		cy.get("@table").find(".grid-selection-toast").should("be.visible");
		cy.get("@table")
			.find(".grid-selection-toast__message")
			.should("contain", "3 row(s) selected");

		// duplicate_rows unchecks the original row — banner should show 1 row(s) selected.
		cy.window()
			.its("cur_frm")
			.then((frm) => {
				frm.get_field("phone_nos").grid.duplicate_rows();
			});

		cy.get("@table")
			.find(".grid-selection-toast__message")
			.should("contain", "3 row(s) selected");
	});

	it("hides selection banner after deleting selected rows", () => {
		cy.visit("/desk/contact/Test Contact");
		cy.get('.frappe-control[data-fieldname="phone_nos"]').as("table");

		cy.get("@table").find('.grid-row[data-idx="1"] .grid-row-check').click({ force: true });
		cy.get("@table").find(".grid-selection-toast").should("be.visible");

		// Click the delete button in the UI so Cypress waits for DOM changes
		cy.get("@table").find(".grid-remove-rows").click({ force: true });

		cy.get("@table").find(".grid-selection-toast").should("not.be.visible");
	});

	it("shows and hides selection banner on selecting and unselecting a row", () => {
		cy.visit("/desk/contact/Test Contact");
		cy.get('.frappe-control[data-fieldname="phone_nos"]').as("table");

		cy.get("@table").find('.grid-row[data-idx="1"] .grid-row-check').click({ force: true });
		cy.get("@table").find(".grid-selection-toast").should("be.visible");

		cy.get("@table").find('.grid-row[data-idx="1"] .grid-row-check').click({ force: true });
		cy.get("@table").find(".grid-selection-toast").should("not.be.visible");
	});
});
