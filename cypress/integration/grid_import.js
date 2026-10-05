context("Child Table Data Import", () => {
	const USER = "grid.import@example.com";
	const PASSWORD = "test_password";
	let contact;

	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.insert_doc(
			"User",
			{
				email: USER,
				first_name: "Grid Import",
				new_password: PASSWORD,
				send_welcome_email: 0,
				roles: [{ role: "Desk User" }],
			},
			true
		);

		cy.login(USER, PASSWORD);
		cy.visit("/desk/website");
		cy.insert_doc("Contact", {
			first_name: "Grid Import",
			phone_nos: Array.from({ length: 5 }, (_, i) => ({ phone: `+91-90000000${i}` })),
		}).then((doc) => (contact = doc.name));
	});

	beforeEach(() => {
		cy.login(USER, PASSWORD);
		cy.visit(`/desk/contact/${contact}`);
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

	const open_import = (import_type = "Insert New Records") => {
		cy.get("@table").find(".grid-upload").should("not.have.class", "hidden").click({
			force: true,
		});
		dialog().find('select[data-fieldname="import_type"]').select(import_type);
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
		attach(rows, header);
		primary("Next");
		cy.wait("@parse_file");
		active_step().should("not.contain", "Upload");
	};

	const active_step = () => dialog().find(".modal-title");

	const skip_all = () =>
		dialog().find("thead .grid-import-skip-cell input").check({ force: true });

	const STEPS = ["Upload", "Fix Issues", "Preview"];

	const step_towards = (label) => {
		active_step()
			.invoke("text")
			.then((text) => {
				const current = STEPS.find((step) => text.trim().startsWith(step));
				if (current === label) return;
				const back = STEPS.indexOf(label) < STEPS.indexOf(current);
				dialog()
					.find(".standard-actions")
					.contains("button", back ? "Back" : "Next")
					.should("not.be.disabled")
					.click({ force: true });
				step_towards(label);
			});
	};

	const go_to_step = (label) => {
		hint().should("not.be.empty");
		step_towards(label);
		active_step().should("contain", label);
	};

	it("adds imported rows alongside the existing ones", () => {
		open_import();
		upload(["9876500001,0", "9876500002,1"]);

		dialog().find(".grid-import-preview-table").should("exist");
		primary("Upload");

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

		skip_all();
		primary("Next");
		primary("Upload");
		cy.contains("1 added, 1 skipped, save to apply").should("exist");

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

			skip_all();
			primary("Next");
			primary("Upload");
			cy.contains("1 updated, 2 skipped, save to apply").should("exist");

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
				hint().should("contain", "0 rows will be updated.").and("not.contain", "note");
				dialog().find("td.has-error").should("not.exist");
				primary("Upload");
				cy.contains("0 updated, 0 skipped, save to apply").should("exist");
			});
	});

	it("counts only the last row for a repeated ID", () => {
		cy.window()
			.its("cur_frm.doc.phone_nos.0")
			.then((first) => {
				open_import("Update Existing Records");
				upload(
					[`${first.name},9876500030`, `${first.name},${first.phone}`],
					"ID,Number (phone)"
				);

				active_step().should("contain", "Preview");
				hint().should("contain", "0 rows will be updated.");
				primary("Upload");
				cy.contains("0 updated, 0 skipped, save to apply").should("exist");
			});
	});

	it("upserts: updates known IDs and adds the rest", () => {
		cy.get("@firstRowId").then((id) => {
			open_import("Insert or Update Records");
			upload([`${id},9876500020,0`, ",9876500021,0"], `ID,${HEADER}`);
			primary("Upload");
			cy.contains("1 added, 1 updated, 0 skipped, save to apply").should("exist");

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
	});

	it("blocks an insert when a mandatory field has no column", () => {
		open_import();
		upload(["1"], "Is Primary Phone (is_primary_phone)");

		hint().should("contain", "In Contact Numbers, Number is required in every row.");
		dialog().find(".btn-modal-primary").should("be.disabled");
	});

	it("blocks only the upserted rows that would be added without a mandatory field", () => {
		cy.get("@firstRowId").then((id) => {
			open_import("Insert or Update Records");
			upload([`${id},1`, ",1"], "ID,Is Primary Phone (is_primary_phone)");

			dialog()
				.find(".grid-import-preview-row .indicator")
				.should("have.length", 1)
				.and("have.attr", "title")
				.and("contain", "In Contact Numbers, Number is required in row");
			dialog().find(".btn-modal-primary").should("be.disabled");

			skip_all();
			primary("Next");
			primary("Upload");

			cy.get("@rowsBefore").then((rows_before) => {
				phone_rows().should("have.length", rows_before);
			});
		});
	});

	it("re-checks the rows when the import type changes after an upload", () => {
		open_import();
		upload(["9876500040,0"]);
		dialog().find(".grid-import-preview-table").should("exist");

		go_to_step("Upload");
		dialog().find('select[data-fieldname="import_type"]').select("Update Existing Records");
		primary("Next");
		cy.wait("@parse_file");

		hint().should("contain", "No column is mapped to ID");
		dialog().find(".grid-import-preview-table tr[data-row]").should("have.length", 1);
	});

	it("marks rows with notes", () => {
		open_import();
		upload(["9876500070,0", "9876500071,0,extra"]);

		hint().should("not.contain", "note");
		dialog().find(".grid-import-preview-row .indicator").should("have.length", 1);
	});

	it("warns about a column with data but no header", () => {
		open_import();
		upload(["9876500080,extra"], "Number (phone),");

		active_step().should("contain", "Fix Issues");
		dialog().find('.grid-import-mapping-row td[data-col="1"] input').focus();
		dialog()
			.find(".grid-import-footer-message")
			.should("contain", "Column 2 has no header and will be ignored.");
	});

	it("marks only the notes on rows the step shows", () => {
		open_import();
		upload(["9876500090,maybe", "9876500091,0,extra"]);

		hint().should("contain", "1 of 2 imported rows have issues.");
		skip_all();
		hint().should("contain", "· 1 skipped.");

		primary("Next");
		dialog().find(".grid-import-preview-row .indicator").should("have.length", 1);
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
		primary("Upload");

		phone_rows().then((rows) => {
			const numbers = rows.map((row) => row.phone);
			expect(numbers).to.include("9876500060");
			expect(numbers).to.include("9876500061");
			expect(numbers).to.not.include("9876500062");
		});
	});

	it("skips a row when its checkbox is ticked and restores it when unticked", () => {
		open_import();
		upload(["9876502000,maybe", "9876502001,maybe"]);

		const skip = () => dialog().find("tr[data-row=2] .grid-import-skip-cell input");
		skip().check({ force: true });
		hint().should("contain", "1 of 2 imported rows have issues · 1 skipped.");
		dialog().find("tr[data-row=2]").should("have.class", "grid-import-skipped-row");
		skip().uncheck({ force: true });
		hint().should("contain", "2 of 2 imported rows have issues.");
		dialog().find("tr[data-row=2]").should("not.have.class", "grid-import-skipped-row");
	});

	it("shows up to 50 rows that need fixing", () => {
		open_import();
		upload(Array.from({ length: 50 }, (_, i) => `98765${1000 + i},maybe`));

		dialog().find(".grid-import-preview-table tr[data-row]").should("have.length", 50);
		hint().should("contain", "50 of 50 imported rows have issues.");
		dialog().find(".grid-import-preview-alert .es-alert").should("not.exist");
	});

	it("skips to Preview when more than 50 rows need fixing", () => {
		open_import();
		upload([
			"9876501100,0",
			"9876501101,0",
			...Array.from({ length: 60 }, (_, i) => `98765${1200 + i},maybe`),
		]);

		dialog()
			.find(".grid-import-preview-alert .es-alert")
			.should("contain", "Too Many Errors")
			.and("contain", "60 of 62 uploaded rows need fixing");
		dialog().find(".grid-import-preview-table").should("not.be.visible");

		primary("Skip Invalid and Continue");
		active_step().should("contain", "Preview");
		hint().should("contain", "2 rows will be added.");
		dialog().find(".grid-import-skip-cell").should("not.exist");
	});

	it("shows only the rows with errors after a column is remapped", () => {
		const map_second_column = (search) => {
			dialog()
				.find('.grid-import-mapping-row td[data-col="1"] input')
				.clear({ force: true })
				.type(search, { force: true });
			cy.get(".awesomplete ul:visible li").first().click({ force: true });
		};

		open_import();
		upload(["call-me,yes", "9876501300,maybe", "9876501301,1"], "Number (phone),Flag");
		dialog().find("tr[data-row]").should("have.length", 1);

		map_second_column("is_primary_phone");
		dialog().find('tr[data-row="3"] td[data-col="1"].has-error').should("exist");
		dialog().find("tr[data-row]").should("have.length", 2);

		map_second_column("Don't Import");
		dialog().find('tr[data-row="3"]').should("not.exist");
		dialog().find("tr[data-row]").should("have.length", 1);
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
		primary("Upload");
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
		primary("Upload");
		phone_rows().then((rows) => {
			const added = rows.find((d) => d.phone === "9876500071");
			expect(added, "row was still imported").to.exist;
			expect(added.is_primary_phone, "restricted value must not apply").to.not.equal(1);
		});
	});
});
