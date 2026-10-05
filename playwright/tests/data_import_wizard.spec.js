import { test, expect } from "../support";

const PREVIEW_METHOD =
	"/api/method/frappe.core.doctype.data_import.data_import.get_preview_from_template";

test.describe("Data Import Wizard", () => {
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

	const open_data_import = async (page, name) => {
		await page.goto(`/desk/data-import/${encodeURIComponent(name)}`);
		await expect(page.locator("body")).toHaveAttribute("data-ajax-state", "complete");
		await expect(page.locator(".data-import-custom-ui")).toBeVisible();
	};

	const open_step = (page, label) =>
		page.getByRole("button", { name: label, exact: true }).click();

	const config_field = (page, fieldname) =>
		page.locator(
			`.data-import-custom-ui .diw-config-step [data-fieldname='${fieldname}']:visible`
		);

	const wizard_import_file_field = (page) => config_field(page, "import_file");

	// Upload-source tabs render via frappe.ui.tabs (.es-tabs / .es-tabs__tab),
	// and only while the source is still selectable (no file attached yet).
	const upload_source_tab = (page, label) =>
		page
			.locator(".data-import-custom-ui .diw-config-step .es-tabs__tab", { hasText: label })
			.first();

	const active_step_panel = (page) => page.locator(".diw-step-panel:not(.hidden)");

	const preview_data_import = (request) => request.postDataJSON()?.data_import;

	const expect_locked_field_value = async (page, fieldname, expected_value) => {
		const field = config_field(page, fieldname);
		await expect(async () => {
			const state = await field.evaluateAll((fields) => {
				const is_visible = (el) => el.getClientRects().length > 0;
				const input = fields
					.flatMap((el) => [...el.querySelectorAll("input, textarea, select")])
					.find(is_visible);
				if (!input) {
					return { text: fields.map((el) => el.textContent).join("") };
				}
				return {
					value: input.value || input.getAttribute("value") || "",
					locked: input.readOnly || input.disabled,
				};
			});

			if ("text" in state) {
				expect(state.text).toContain(expected_value);
				return;
			}
			expect(state.value).toContain(expected_value);
			expect(state.locked).toBe(true);
		}).toPass();
	};

	test.beforeAll(async ({ admin }) => {
		const ts = Date.now();
		test_file_name = `wizard-test-${ts}.csv`;
		second_file_name = `wizard-test-second-${ts}.csv`;
		const csv_content = `First Name,Last Name\n${first_preview_value},Tester\n`;
		const second_csv_content = `First Name,Last Name\n${second_preview_value},Tester\n`;

		const insert_file = async (file_name, content) =>
			(await admin.insert_doc("File", { file_name, is_private: 1, content })).file_url;
		const insert_data_import = async () =>
			(
				await admin.insert_doc("Data Import", {
					reference_doctype: "Contact",
					import_type: "Insert New Records",
				})
			).name;
		const db_set_values = (name, values) =>
			admin.call("frappe.tests.ui_test_helpers.db_set_values", {
				doctype: "Data Import",
				name,
				values,
			});

		test_file_url = await insert_file(test_file_name, csv_content);
		second_file_url = await insert_file(second_file_name, second_csv_content);

		import_with_file = await insert_data_import();
		await admin.update_doc("Data Import", import_with_file, { import_file: test_file_url });

		import_without_file = await insert_data_import();

		import_with_second_file = await insert_data_import();
		await admin.update_doc("Data Import", import_with_second_file, {
			import_file: second_file_url,
		});

		import_success_with_file = await insert_data_import();
		await db_set_values(import_success_with_file, {
			import_file: test_file_url,
			status: "Success",
			custom_delimiters: 1,
			delimiter_options: ";",
			use_csv_sniffer: 1,
		});

		import_partial_with_sheet = await insert_data_import();
		await db_set_values(import_partial_with_sheet, {
			google_sheets_url: public_google_sheet_url,
			status: "Partial Success",
			custom_delimiters: 1,
			delimiter_options: "|",
			use_csv_sniffer: 1,
		});
	});

	test.afterAll(async ({ admin }) => {
		const data_imports = [
			import_with_file,
			import_without_file,
			import_with_second_file,
			import_success_with_file,
			import_partial_with_sheet,
		];
		for (const name of data_imports.filter(Boolean)) {
			await admin.remove_doc("Data Import", name, true);
		}
		for (const file_name of [test_file_name, second_file_name].filter(Boolean)) {
			const r = await admin.get_list("File", ["name"], [["file_name", "=", file_name]]);
			const name = r.data?.[0]?.name;
			if (name) {
				await admin.remove_doc("File", name, true);
			}
		}
	});

	test.beforeEach(async ({ desk }) => {
		await desk.login("Administrator");
	});

	test("does not leak attached file across documents and locks the source once a file is attached", async ({
		page,
	}) => {
		await open_data_import(page, import_with_file);

		await open_step(page, "Config");
		const file_card_name = wizard_import_file_field(page).locator(
			".diw-import-file-card-name:visible"
		);
		await expect(file_card_name).toBeVisible();
		await expect(file_card_name).toContainText(test_file_name);
		await expect(page.locator(".data-import-custom-ui .diw-config-step .es-tabs")).toHaveCount(
			0
		);
		await expect(
			page.locator('[data-fieldname="google_sheets_url"] input:visible')
		).toHaveCount(0);

		await open_data_import(page, import_without_file);

		await open_step(page, "Config");
		await expect(file_card_name).toHaveCount(0);
		await expect(wizard_import_file_field(page).locator(".btn-attach")).not.toHaveCount(0);
		await upload_source_tab(page, "Google Sheet").click();
		await expect(
			page.locator('[data-fieldname="google_sheets_url"] input:visible')
		).not.toHaveCount(0);
	});

	test("ignores stale delayed preview responses after switching documents", async ({ page }) => {
		await page.route(`**${PREVIEW_METHOD}`, async (route) => {
			if (preview_data_import(route.request()) !== import_with_file) {
				await route.continue();
				return;
			}
			try {
				const response = await route.fetch();
				await new Promise((resolve) => setTimeout(resolve, 2500));
				await route.fulfill({ response });
			} catch {
				// the page moved on before the delayed response was delivered
			}
		});

		await open_data_import(page, import_with_file);
		const preview_b = page.waitForResponse(
			(res) =>
				res.url().includes(PREVIEW_METHOD) &&
				preview_data_import(res.request()) === import_with_second_file
		);
		await open_data_import(page, import_with_second_file);

		await preview_b;

		await open_step(page, "Preview");
		await expect(active_step_panel(page)).toContainText(second_preview_value);
		await expect(active_step_panel(page)).not.toContainText(first_preview_value);
	});

	test("keeps the Import step locked until import has started", async ({ page }) => {
		await open_data_import(page, import_with_file);

		await open_step(page, "Preview");
		await page.getByRole("button", { name: "Fix issues", exact: true }).click();
		await expect(active_step_panel(page)).toHaveAttribute("data-step", "2");

		// The step label lives in its own span; match it exactly, then act on the
		// button. Locked steps are exposed semantically (aria-disabled/data-state),
		// not via a styling class.
		const import_step = page.locator(".diw-stepper-wrap .es-stepper__step").filter({
			has: page.locator(".es-stepper__label", { hasText: /^Import$/ }),
		});
		await expect(import_step).toHaveAttribute("aria-disabled", "true");
		await expect(import_step).toHaveAttribute("data-state", "locked");
		await import_step.click({ force: true });
		await expect(
			page.getByText("Start the import before opening the Import step.").first()
		).toBeVisible();
		await expect(active_step_panel(page)).toHaveAttribute("data-step", "2");
		await expect(active_step_panel(page)).not.toContainText("Loading import log");
	});

	test("locks source fields and CSV controls after finished imports", async ({ page }) => {
		await open_data_import(page, import_success_with_file);

		await open_step(page, "Config");
		await expect(
			wizard_import_file_field(page).locator(".diw-import-file-card-name:visible")
		).toContainText(test_file_name);
		// Locked file: the card renders no Clear button, and no attach control is
		// exposed. (The underlying Attach control keeps its own clear/attach nodes in
		// the DOM but hidden, so assert on the card / on visibility, not on text.)
		await expect(wizard_import_file_field(page).locator(".diw-import-file-clear")).toHaveCount(
			0
		);
		await expect(wizard_import_file_field(page).locator(".btn-attach:visible")).toHaveCount(0);
		await expect(
			page.locator('[data-fieldname="custom_delimiters"] input[type="checkbox"]:visible')
		).toBeDisabled();
		await expect_locked_field_value(page, "delimiter_options", ";");
		await expect(
			page.locator('[data-fieldname="use_csv_sniffer"] input[type="checkbox"]:visible')
		).toBeDisabled();

		await open_data_import(page, import_partial_with_sheet);

		await open_step(page, "Config");
		await expect_locked_field_value(page, "google_sheets_url", public_google_sheet_url);
		await expect(
			page.locator('[data-fieldname="custom_delimiters"] input[type="checkbox"]:visible')
		).toBeDisabled();
		await expect_locked_field_value(page, "delimiter_options", "|");
		await expect(
			page.locator('[data-fieldname="use_csv_sniffer"] input[type="checkbox"]:visible')
		).toBeDisabled();
	});
});
