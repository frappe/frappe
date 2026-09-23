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
				cy.wrap(frm.doc.phone_nos[0].name).as("firstRowId");
			});
		cy.get('.frappe-control[data-fieldname="phone_nos"]').as("table");
		cy.intercept("POST", "/api/method/frappe.desk.form.grid_import.parse_file").as(
			"parse_file"
		);
	});

	const HEADER = "Number (phone),Is Primary Phone (is_primary_phone)";
	const dialog = () => cy.get(".grid-import-dialog:visible");
	const hint = () => dialog().find(".grid-import-preview-hint");
	const phone_rows = () => cy.window().its("cur_frm.doc.phone_nos");
	const primary = (label) =>
		dialog()
			.find(".standard-actions .btn-modal-primary")
			.should("contain", label)
			.and("not.be.disabled")
			.click({ force: true });

	const open_import = (import_type) => {
		cy.get("@table").find(".grid-upload").should("not.have.class", "hidden").click({
			force: true,
		});
		dialog().should("exist");
		if (import_type) {
			dialog().find('select[data-fieldname="import_type"]').select(import_type);
		}
	};

	const attach = (rows, header = HEADER) => {
		dialog()
			.find(".file-upload-area")
			.selectFile(
				{
					contents: Cypress.Buffer.from([header, ...rows].join("\n")),
					fileName: "phone_nos.csv",
					mimeType: "text/csv",
				},
				{ action: "drag-drop" }
			);
	};

	const upload = (rows, header = HEADER) => {
		primary("Next");
		attach(rows, header);
		primary("Next");
		cy.wait("@parse_file");
		active_step().should("not.contain", "Upload");
	};

	const active_step = () => dialog().find(".es-stepper [aria-current]");

	const go_to_step = (label) => {
		hint().should("not.be.empty");
		dialog()
			.find(".es-stepper__label")
			.contains(new RegExp(`^${label}$`))
			.click();
		active_step().should("contain", label);
	};

	it("adds imported rows alongside the existing ones", () => {
		open_import();
		upload(["9876500001,0", "9876500002,1"]);

		dialog().find(".grid-import-preview-table").should("exist");
		primary("Apply");

		cy.get("@rowsBefore").then((rows_before) => {
			phone_rows().should("have.length", rows_before + 2);
		});
		phone_rows().then((rows) => {
			const numbers = rows.map((row) => row.phone);
			expect(numbers).to.include("9876500001");
			expect(numbers).to.include("9876500002");
		});
	});

	it("stops on Fix Issues when a cell fails validation", () => {
		open_import();
		upload(["9876500003,maybe", "9876500004,0"]);

		dialog()
			.find('td[data-col="1"].has-error select option')
			.then(($options) => [...$options].map((o) => o.value))
			.should("deep.equal", ["maybe", "0", "1"]);
		dialog().find(".btn-modal-primary").should("be.disabled");

		dialog().find('td[data-col="1"].has-error select').select("1", { force: true });
		dialog().find("td.has-error").should("not.exist");
		dialog().find(".btn-modal-primary").should("not.be.disabled");
	});

	it("lets a bad row be skipped instead of fixed", () => {
		open_import();
		upload(["9876500003,maybe", "9876500004,0"]);

		dialog().find(".grid-import-skip-all").click({ force: true });
		primary("Next");
		primary("Apply");

		cy.get("@rowsBefore").then((rows_before) => {
			phone_rows().should("have.length", rows_before + 1);
		});
		phone_rows().then((rows) => {
			const numbers = rows.map((row) => row.phone);
			expect(numbers).to.include("9876500004");
			expect(numbers).to.not.include("9876500003");
		});
	});

	it("updates the row matching the ID and flags blank or unmatched IDs", () => {
		cy.get("@firstRowId").then((id) => {
			open_import("Update Existing Records");
			upload(
				[`${id},9876500010,1`, "no-such-row,9876500011,0", ",9876500012,0"],
				`ID,${HEADER}`
			);

			const id_cell = (row) =>
				dialog().find(`tr[data-row="${row}"] td[data-col="0"].has-error`);
			const message = () => dialog().find(".grid-import-footer-message");
			dialog().find(".btn-modal-primary").should("be.disabled");
			id_cell(3).find("input").click({ force: true });
			message().should("contain", 'No row in this table has the ID "no-such-row".');
			id_cell(4).find("input").click({ force: true });
			message().should("contain", "This field is mandatory and is blank.");

			dialog().find(".grid-import-skip-all").click({ force: true });
			primary("Next");
			primary("Apply");
			cy.contains("0 added, 1 updated, 2 skipped, save to apply").should("exist");

			cy.get("@rowsBefore").then((rows_before) => {
				phone_rows().should("have.length", rows_before);
			});
			phone_rows().then((rows) => {
				const row = rows.find((d) => d.name === id);
				expect(row.phone).to.equal("9876500010");
				expect(row.is_primary_phone).to.equal(1);
				const numbers = rows.map((d) => d.phone);
				expect(numbers).to.not.include("9876500011");
				expect(numbers).to.not.include("9876500012");
			});
		});
	});

	it("updates without mandatory columns and does not count unchanged rows", () => {
		cy.window()
			.its("cur_frm.doc.phone_nos.0")
			.then((first) => {
				open_import("Update Existing Records");
				upload(
					[`${first.name},${first.is_primary_phone}`],
					"ID,Is Primary Phone (is_primary_phone)"
				);

				active_step().should("contain", "Preview");
				hint()
					.should("contain", "1 of 1 rows ready to import.")
					.and("not.contain", "note");
				dialog().find("td.has-error").should("not.exist");
				primary("Apply");
				cy.contains("0 added, 0 updated, 0 skipped, save to apply").should("exist");
			});
	});

	it("upserts: updates known IDs and adds the rest", () => {
		cy.get("@firstRowId").then((id) => {
			open_import("Insert or Update Records");
			upload([`${id},9876500020,0`, ",9876500021,0"], `ID,${HEADER}`);
			primary("Apply");

			cy.get("@rowsBefore").then((rows_before) => {
				phone_rows().should("have.length", rows_before + 1);
			});
			phone_rows().then((rows) => {
				expect(rows.find((d) => d.name === id).phone).to.equal("9876500020");
				expect(rows.map((d) => d.phone)).to.include("9876500021");
			});
		});
	});

	it("blocks an update when no column is mapped to ID", () => {
		open_import("Update Existing Records");
		upload(["9876500030,0"]);

		hint().should("contain", "No column is mapped to ID");
		dialog().find(".btn-modal-primary").should("be.disabled");
		dialog().find(".grid-import-skip-all").should("be.disabled");
	});

	it("blocks an insert when a mandatory field has no column", () => {
		open_import();
		upload(["1"], "Is Primary Phone (is_primary_phone)");

		hint().should("contain", "In Contact Numbers, Number is required in every row.");
		dialog().find(".btn-modal-primary").should("be.disabled");
		dialog().find(".grid-import-skip-all").should("be.disabled");
	});

	it("blocks only the upserted rows that would be added without a mandatory field", () => {
		cy.get("@firstRowId").then((id) => {
			open_import("Insert or Update Records");
			upload([`${id},1`, ",1"], "ID,Is Primary Phone (is_primary_phone)");

			dialog()
				.find(".grid-import-preview-row.has-note")
				.should("have.length", 1)
				.and("have.attr", "title")
				.and("contain", "In Contact Numbers, Number is required in row");
			dialog().find(".btn-modal-primary").should("be.disabled");

			dialog().find(".grid-import-skip-all").click({ force: true });
			primary("Next");
			primary("Apply");

			cy.get("@rowsBefore").then((rows_before) => {
				phone_rows().should("have.length", rows_before);
			});
		});
	});

	it("re-checks the rows when the import type changes after an upload", () => {
		open_import();
		upload(["9876500040,0"]);
		dialog().find(".grid-import-preview-table").should("exist");

		go_to_step("Setup");
		dialog().find('select[data-fieldname="import_type"]').select("Update Existing Records");
		primary("Next");
		primary("Next");
		cy.wait("@parse_file");

		hint().should("contain", "No column is mapped to ID");
		dialog().find(".grid-import-preview-table tr[data-row]").should("have.length", 1);
	});

	it("counts rows with notes in the hint", () => {
		open_import();
		upload(["9876500070,0", "9876500071,0,extra"]);

		hint().should("contain", "1 row has a note");
		dialog().find(".grid-import-preview-row.has-note").should("have.length", 1);
	});

	it("counts only the notes on rows the step shows", () => {
		open_import();
		upload(["9876500090,maybe", "9876500091,0,extra"]);

		hint().should("contain", "1 needs fixing").and("not.contain", "note");
		dialog().find(".grid-import-skip-all").click({ force: true });
		hint().should("contain", "Nothing left to fix").and("not.contain", "note");

		primary("Next");
		hint().should("contain", "1 row has a note");
		dialog().find(".grid-import-preview-row.has-note").should("have.length", 1);
	});

	it("does not let two columns fill the same field", () => {
		open_import();
		upload(["9876500050,9876500051"], "Number (phone),Number");

		hint().should("contain", "Two columns map to the same field");
		dialog().find(".grid-import-mapping-row td.has-error").should("have.length", 2);
		dialog().find(".btn-modal-primary").should("be.disabled");
	});

	it("reads the Google Sheet when that tab is active, even with a file attached", () => {
		cy.intercept("POST", "/api/method/frappe.desk.form.grid_import.parse_google_sheet", {
			body: { message: [["Number (phone)"], ["9876500060"], ["9876500061"]] },
		}).as("parse_google_sheet");

		open_import();
		upload(["9876500062,0"]);
		go_to_step("Upload");

		dialog().find(".grid-import-upload-tabs").contains("Google Sheet").click();
		dialog()
			.find('[data-fieldname="google_sheets_url"] input')
			.type("https://docs.google.com/spreadsheets/d/abc/edit#gid=0", { delay: 0 });
		primary("Next");
		cy.wait("@parse_google_sheet");
		primary("Apply");

		phone_rows().then((rows) => {
			const numbers = rows.map((row) => row.phone);
			expect(numbers).to.include("9876500060");
			expect(numbers).to.include("9876500061");
			expect(numbers).to.not.include("9876500062");
		});
	});

	it("keeps skipped rows and column mapping when paging", () => {
		open_import();
		upload(Array.from({ length: 60 }, (_, i) => `98765${2000 + i},maybe`));

		dialog().find("tr[data-row]").first().invoke("attr", "data-row").as("rowNumber");
		cy.get("@rowNumber").then((row) => {
			dialog()
				.find(`tr[data-row=${row}] .grid-import-skip-cell button`)
				.click({ force: true });
			hint().should("contain", "59 need fixing");
			dialog().find(`tr[data-row=${row}]`).should("have.class", "grid-import-skipped-row");

			dialog()
				.find(".grid-import-mapping-row td[data-col=1] input")
				.clear({ force: true })
				.type("Don't Import", { force: true })
				.blur();
			dialog().find("th[data-col=1]").should("have.attr", "data-mapped", "0");

			dialog().find(".last-page").click({ force: true });
			dialog().find(".first-page").click({ force: true });

			dialog().find(`tr[data-row=${row}]`).should("have.class", "grid-import-skipped-row");
			dialog().find("th[data-col=1]").should("have.attr", "data-mapped", "0");
			dialog()
				.find(".grid-import-mapping-row td[data-col=1] input")
				.should("have.value", "Don't Import");
		});
	});

	it("pager buttons stop at the first and last page", () => {
		open_import();
		upload(Array.from({ length: 100 }, (_, i) => `98765${3000 + i},maybe`));

		const page_box = () => dialog().find(".current-page-number");
		dialog().find(".total-page-number").should("contain", "2");
		dialog().find(".last-page").click({ force: true });
		page_box().should("have.value", "2");
		page_box().should(($i) => expect($i[0].scrollWidth).to.be.at.most($i[0].clientWidth));
		dialog().find(".next-page").click({ force: true });
		page_box().should("have.value", "2");
		dialog().find(".prev-page").click({ force: true });
		page_box().should("have.value", "1");
		dialog().find(".prev-page").click({ force: true });
		page_box().should("have.value", "1");
		dialog().find("tr[data-row]").should("have.length", 50);
	});

	it("pages Fix Issues when more than 50 rows need fixing", () => {
		const bad_rows = Array.from({ length: 60 }, (_, i) => `98765${1000 + i},maybe`);
		open_import();
		upload(bad_rows);

		dialog().find(".grid-import-preview-table tr[data-row]").should("have.length", 50);
		dialog().find(".grid-import-preview-foot .grid-pagination").should("be.visible");
		hint().should("contain", "60 need fixing");
	});

	const restrict_is_primary_phone = () =>
		cy.window().then((win) => {
			win.frappe.meta.get_docfield("Contact Phone", "is_primary_phone").permlevel = 1;
			expect(win.cur_frm.get_perm(1, "write")).to.not.be.ok;
		});

	it("does not map a column whose permlevel the user cannot write", () => {
		restrict_is_primary_phone();
		open_import();
		upload(["9876500070,1"]);

		dialog().find(".grid-import-mapping-row").should("exist");
		dialog()
			.find('th[data-col="1"]')
			.should("not.have.class", "has-error")
			.and("have.attr", "data-mapped", "0");
		dialog()
			.find('.grid-import-mapping-row td[data-col="1"] input')
			.should("have.value", "Don't Import")
			.click();
		dialog().find(".grid-import-footer-message").should("contain", "does not match a field");

		go_to_step("Preview");
		primary("Apply");
		phone_rows().then((rows) => {
			const added = rows.find((d) => d.phone === "9876500070");
			expect(added, "row was still imported").to.exist;
			expect(added.is_primary_phone, "restricted value must not apply").to.not.equal(1);
		});
	});

	it("ignores a restricted field typed into the mapping box", () => {
		restrict_is_primary_phone();
		open_import();
		upload(["9876500071,1"]);

		dialog()
			.find('.grid-import-mapping-row td[data-col="1"] input')
			.clear()
			.type("is_primary_phone", { delay: 0 })
			.blur();
		dialog()
			.find('th[data-col="1"]')
			.should("not.have.class", "has-error")
			.and("have.attr", "data-mapped", "0");

		go_to_step("Preview");
		primary("Apply");
		phone_rows().then((rows) => {
			const added = rows.find((d) => d.phone === "9876500071");
			expect(added, "row was still imported").to.exist;
			expect(added.is_primary_phone, "restricted value must not apply").to.not.equal(1);
		});
	});
});
