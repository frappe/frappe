context("Data Import Wizard", () => {
	let import_with_file = null;
	let import_without_file = null;
	let import_with_second_file = null;
	let import_success_with_file = null;
	let import_partial_with_sheet = null;
	let test_file_name = null;
	let test_file_url = null;
	let second_file_name = null;
	let second_file_url = null;
	const first_preview_value = "AlphaPreviewRow";
	const second_preview_value = "BetaPreviewRow";
	const public_google_sheet_url =
		"https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0";

	const open_data_import = (name) => {
		cy.visit(`/desk/data-import/${encodeURIComponent(name)}`);
		cy.get("body").should("have.attr", "data-ajax-state", "complete");
		cy.get(".data-import-custom-ui").should("be.visible");
	};

	const wizard_import_file_field = () =>
		cy.get(".data-import-custom-ui .diw-config-step [data-fieldname='import_file']:visible");

	// Upload-source tabs render via frappe.ui.tabs (.es-tabs / .es-tabs__tab),
	// and only while the source is still selectable (no file attached yet).
	const upload_source_tab = (label) =>
		cy.get(".data-import-custom-ui .diw-config-step .es-tabs__tab").contains(label);

	const active_step_panel = () => cy.get(".diw-step-panel").not(".hidden");

	const expect_locked_field_value = (fieldname, expected_value) => {
		cy.get(
			`.data-import-custom-ui .diw-config-step [data-fieldname='${fieldname}']:visible`
		).then(($field) => {
			const $inputs = $field.find("input:visible, textarea:visible, select:visible");
			if ($inputs.length) {
				const input = $inputs.first();
				expect(input.val() || input.attr("value") || "").to.contain(expected_value);
				expect(input.prop("readOnly") || input.prop("disabled")).to.eq(true);
				return;
			}

			expect($field.text()).to.contain(expected_value);
		});
	};

	before(() => {
		cy.login("Administrator", "admin");
		cy.visit("/desk");

		const ts = Date.now();
		test_file_name = `wizard-test-${ts}.csv`;
		second_file_name = `wizard-test-second-${ts}.csv`;
		const csv_content = `First Name,Last Name\n${first_preview_value},Tester\n`;
		const second_csv_content = `First Name,Last Name\n${second_preview_value},Tester\n`;

		cy.insert_doc("File", {
			doctype: "File",
			file_name: test_file_name,
			is_private: 1,
			content: csv_content,
		})
			.then((file_doc) => {
				test_file_url = file_doc.file_url;

				return cy.insert_doc("File", {
					doctype: "File",
					file_name: second_file_name,
					is_private: 1,
					content: second_csv_content,
				});
			})
			.then((file_doc) => {
				second_file_url = file_doc.file_url;

				return cy.insert_doc("Data Import", {
					doctype: "Data Import",
					reference_doctype: "Contact",
					import_type: "Insert New Records",
				});
			})
			.then((doc) => {
				import_with_file = doc.name;
				return cy.update_doc("Data Import", import_with_file, {
					import_file: test_file_url,
				});
			})
			.then(() => {
				return cy.insert_doc("Data Import", {
					doctype: "Data Import",
					reference_doctype: "Contact",
					import_type: "Insert New Records",
				});
			})
			.then((doc) => {
				import_without_file = doc.name;
				return cy.insert_doc("Data Import", {
					doctype: "Data Import",
					reference_doctype: "Contact",
					import_type: "Insert New Records",
				});
			})
			.then((doc) => {
				import_with_second_file = doc.name;
				return cy.update_doc("Data Import", import_with_second_file, {
					import_file: second_file_url,
				});
			})
			.then(() => {
				return cy.insert_doc("Data Import", {
					doctype: "Data Import",
					reference_doctype: "Contact",
					import_type: "Insert New Records",
				});
			})
			.then((doc) => {
				import_success_with_file = doc.name;
				return cy.call("frappe.tests.ui_test_helpers.db_set_values", {
					doctype: "Data Import",
					name: import_success_with_file,
					values: {
						import_file: test_file_url,
						status: "Success",
						custom_delimiters: 1,
						delimiter_options: ";",
						use_csv_sniffer: 1,
					},
				});
			})
			.then(() => {
				return cy.insert_doc("Data Import", {
					doctype: "Data Import",
					reference_doctype: "Contact",
					import_type: "Insert New Records",
				});
			})
			.then((doc) => {
				import_partial_with_sheet = doc.name;
				return cy.call("frappe.tests.ui_test_helpers.db_set_values", {
					doctype: "Data Import",
					name: import_partial_with_sheet,
					values: {
						google_sheets_url: public_google_sheet_url,
						status: "Partial Success",
						custom_delimiters: 1,
						delimiter_options: "|",
						use_csv_sniffer: 1,
					},
				});
			});
	});

	after(() => {
		cy.login("Administrator", "admin");
		cy.visit("/desk");
		if (import_with_file) {
			cy.remove_doc("Data Import", import_with_file, true);
		}
		if (import_without_file) {
			cy.remove_doc("Data Import", import_without_file, true);
		}
		if (import_with_second_file) {
			cy.remove_doc("Data Import", import_with_second_file, true);
		}
		if (import_success_with_file) {
			cy.remove_doc("Data Import", import_success_with_file, true);
		}
		if (import_partial_with_sheet) {
			cy.remove_doc("Data Import", import_partial_with_sheet, true);
		}
		if (test_file_name) {
			cy.get_list("File", ["name"], [["file_name", "=", test_file_name]]).then((r) => {
				const file_name = r.data?.[0]?.name;
				if (file_name) {
					cy.remove_doc("File", file_name, true);
				}
			});
		}
		if (second_file_name) {
			cy.get_list("File", ["name"], [["file_name", "=", second_file_name]]).then((r) => {
				const file_name = r.data?.[0]?.name;
				if (file_name) {
					cy.remove_doc("File", file_name, true);
				}
			});
		}
	});

	it("does not leak attached file across documents and locks the source once a file is attached", () => {
		open_data_import(import_with_file);

		cy.findByRole("button", { name: "Config" }).click({ force: true });
		wizard_import_file_field()
			.find(".diw-import-file-card-name:visible")
			.should("be.visible")
			.and("contain", test_file_name);
		// Once a file is attached the source is fixed: no upload-source tabs are
		// rendered and the Google Sheet field stays hidden.
		cy.get(".data-import-custom-ui .diw-config-step .es-tabs").should("not.exist");
		cy.get('[data-fieldname="google_sheets_url"] input:visible').should("not.exist");

		open_data_import(import_without_file);

		cy.findByRole("button", { name: "Config" }).click({ force: true });
		wizard_import_file_field().find(".diw-import-file-card-name:visible").should("not.exist");
		wizard_import_file_field().find(".btn-attach").should("exist");
		// With no file attached the source is still selectable via the tab buttons.
		upload_source_tab("Google Sheet").click({ force: true });
		cy.get('[data-fieldname="google_sheets_url"] input:visible').should("exist");
	});

	it("ignores stale delayed preview responses after switching documents", () => {
		cy.intercept(
			"POST",
			"**/api/method/frappe.core.doctype.data_import.data_import.get_preview_from_template",
			(req) => {
				const data_import = req.body?.data_import;
				if (data_import === import_with_file) {
					req.alias = "previewA";
					req.reply((res) => {
						res.delay = 2500;
					});
					return;
				}

				if (data_import === import_with_second_file) {
					req.alias = "previewB";
				}

				req.continue();
			}
		);

		open_data_import(import_with_file);
		open_data_import(import_with_second_file);

		cy.wait("@previewB");
		cy.wait(3000);

		cy.findByRole("button", { name: "Preview" }).click({ force: true });
		active_step_panel().should("contain.text", second_preview_value);
		active_step_panel().should("not.contain.text", first_preview_value);
	});

	it("keeps the Import step locked until import has started", () => {
		open_data_import(import_with_file);

		cy.findByRole("button", { name: "Preview" }).click({ force: true });
		cy.findByRole("button", { name: "Fix issues" }).click({ force: true });
		active_step_panel().should("have.attr", "data-step", "2");

		// The step label lives in its own span; match it exactly, then act on the
		// button. Locked steps are exposed semantically (aria-disabled/data-state),
		// not via a styling class.
		cy.contains(".diw-stepper-wrap .es-stepper__label", /^Import$/)
			.closest(".es-stepper__step")
			.should("have.attr", "aria-disabled", "true")
			.should("have.attr", "data-state", "locked")
			.click({ force: true });
		cy.contains("Start the import before opening the Import step.").should("be.visible");
		active_step_panel().should("have.attr", "data-step", "2");
		active_step_panel().should("not.contain.text", "Loading import log");
	});

	it("locks source fields and CSV controls after finished imports", () => {
		open_data_import(import_success_with_file);

		cy.findByRole("button", { name: "Config" }).click({ force: true });
		wizard_import_file_field()
			.find(".diw-import-file-card-name:visible")
			.should("contain", test_file_name);
		// Locked file: the card renders no Clear button, and no attach control is
		// exposed. (The underlying Attach control keeps its own clear/attach nodes in
		// the DOM but hidden, so assert on the card / on visibility, not on text.)
		wizard_import_file_field().find(".diw-import-file-clear").should("not.exist");
		wizard_import_file_field().find(".btn-attach:visible").should("not.exist");
		cy.get('[data-fieldname="custom_delimiters"] input[type="checkbox"]:visible').should(
			"be.disabled"
		);
		expect_locked_field_value("delimiter_options", ";");
		cy.get('[data-fieldname="use_csv_sniffer"] input[type="checkbox"]:visible').should(
			"be.disabled"
		);

		open_data_import(import_partial_with_sheet);

		cy.findByRole("button", { name: "Config" }).click({ force: true });
		expect_locked_field_value("google_sheets_url", public_google_sheet_url);
		cy.get('[data-fieldname="custom_delimiters"] input[type="checkbox"]:visible').should(
			"be.disabled"
		);
		expect_locked_field_value("delimiter_options", "|");
		cy.get('[data-fieldname="use_csv_sniffer"] input[type="checkbox"]:visible').should(
			"be.disabled"
		);
	});
});
