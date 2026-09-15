context("Child Table Data Import", () => {
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

	beforeEach(() => {
		cy.login();
		cy.visit("/desk/contact/Test Contact");
		cy.window()
			.its("cur_frm")
			.then((frm) => {
				frm.get_docfield("phone_nos").allow_bulk_edit = 1;
				frm.get_field("phone_nos").grid.setup_allow_bulk_edit();
				cy.wrap(frm.doc.phone_nos.length).as("rowsBefore");
			});
		cy.get('.frappe-control[data-fieldname="phone_nos"]').as("table");
		cy.intercept("POST", "/api/method/frappe.desk.form.grid_import.parse_file").as(
			"parse_file"
		);
	});

	const open_import = () => {
		cy.get("@table").find(".grid-upload").should("not.have.class", "hidden").click({
			force: true,
		});
		cy.get(".grid-import-dialog:visible").should("exist");
	};

	const upload = (rows) => {
		const csv = ["Number (phone),Is Primary Phone (is_primary_phone)", ...rows].join("\n");
		cy.click_modal_primary_button("Next");
		cy.get(".grid-import-dialog:visible")
			.find(".file-upload-area")
			.selectFile(
				{
					contents: Cypress.Buffer.from(csv),
					fileName: "phone_nos.csv",
					mimeType: "text/csv",
				},
				{ action: "drag-drop" }
			);
		cy.click_modal_primary_button("Upload");
		cy.wait("@parse_file");
	};

	it("adds imported rows alongside the existing ones", () => {
		open_import();
		upload(["9876500001,0", "9876500002,1"]);

		cy.get(".grid-import-dialog:visible").find(".grid-import-preview-table").should("exist");
		cy.click_modal_primary_button("Apply");

		cy.get("@rowsBefore").then((rows_before) => {
			cy.window()
				.its("cur_frm.doc.phone_nos")
				.should("have.length", rows_before + 2);
		});
		cy.window()
			.its("cur_frm.doc.phone_nos")
			.then((rows) => {
				const numbers = rows.map((row) => row.phone);
				expect(numbers).to.include("9876500001");
				expect(numbers).to.include("9876500002");
			});
	});

	it("stops on Fix Issues when a cell fails validation", () => {
		open_import();
		upload(["9876500003,maybe", "9876500004,0"]);

		cy.get(".grid-import-dialog:visible").find(".grid-import-pending-cell").should("exist");
		cy.get(".grid-import-dialog:visible").find(".btn-modal-primary").should("be.disabled");
	});

	it("lets a bad row be skipped instead of fixed", () => {
		open_import();
		upload(["9876500003,maybe", "9876500004,0"]);

		cy.get(".grid-import-dialog:visible").find(".grid-import-skip-all").click({ force: true });
		cy.click_modal_primary_button("Next");
		cy.click_modal_primary_button("Apply");

		cy.get("@rowsBefore").then((rows_before) => {
			cy.window()
				.its("cur_frm.doc.phone_nos")
				.should("have.length", rows_before + 1);
		});
		cy.window()
			.its("cur_frm.doc.phone_nos")
			.then((rows) => {
				const numbers = rows.map((row) => row.phone);
				expect(numbers).to.include("9876500004");
				expect(numbers).to.not.include("9876500003");
			});
	});
});
