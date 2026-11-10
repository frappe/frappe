import { test, expect } from "../support";

const GET_IMPORT_FIELDS =
	"**/api/method/frappe.core.doctype.data_import.data_import.get_import_fields";

// Contact has no import provider, so answer the form's schema request with one: the picker and
// preview then read their fields from it, as they do for a DocType an app registers a provider for.
const provider_schema = {
	fields: [
		{ fieldname: "first_name", label: "First Name", fieldtype: "Data", parent: "Contact" },
		{ fieldname: "last_name", label: "Last Name", fieldtype: "Data", parent: "Contact" },
	],
	child_tables: [],
};

test.describe("Data Import for a DocType with an import provider", () => {
	const data_imports = {};
	let file_name = null;

	const open_data_import = async (page, name) => {
		await page.goto(`/desk/data-import/${encodeURIComponent(name)}`);
		await expect(page.locator("body")).toHaveAttribute("data-ajax-state", "complete");
		await expect(page.locator(".data-import-custom-ui")).toBeVisible();
	};

	test.beforeAll(async ({ admin }) => {
		file_name = `provider-id-${Date.now()}.csv`;
		const { file_url } = await admin.insert_doc("File", {
			file_name,
			is_private: 1,
			content: "ID,First Name\nprovider-id-contact,Alpha\n",
		});

		const insert_data_import = async (import_type) =>
			(await admin.insert_doc("Data Import", { reference_doctype: "Contact", import_type }))
				.name;
		data_imports.insert = await insert_data_import("Insert New Records");
		data_imports.update = await insert_data_import("Update Existing Records");
		data_imports.update_with_file = await insert_data_import("Update Existing Records");
		await admin.update_doc("Data Import", data_imports.update_with_file, {
			import_file: file_url,
		});
	});

	test.afterAll(async ({ admin }) => {
		for (const name of Object.values(data_imports)) {
			await admin.remove_doc("Data Import", name, true);
		}
		const r = await admin.get_list("File", ["name"], [["file_name", "=", file_name]]);
		if (r.data?.[0]?.name) {
			await admin.remove_doc("File", r.data[0].name, true);
		}
	});

	test.beforeEach(async ({ page }) => {
		await page.route(GET_IMPORT_FIELDS, (route) =>
			route.fulfill({ json: { message: provider_schema } })
		);
	});

	test("export picker offers ID when updating, not when inserting", async ({ page }) => {
		for (const [name, offers_id] of [
			[data_imports.update, true],
			[data_imports.insert, false],
		]) {
			await open_data_import(page, name);
			await page.getByRole("button", { name: "Download Template" }).click();

			const dialog = page.locator(".modal:visible", { hasText: "Export Data" });
			await expect(dialog.getByText("First Name", { exact: true })).toBeVisible();
			const id_checkbox = dialog.locator('input[type="checkbox"][data-unit="name"]');
			if (offers_id) {
				await expect(id_checkbox).toBeChecked();
			} else {
				await expect(id_checkbox).toHaveCount(0);
			}
			await page.keyboard.press("Escape");
		}
	});

	test("import preview maps the ID column", async ({ page }) => {
		await open_data_import(page, data_imports.update_with_file);
		await page.getByRole("button", { name: "Preview", exact: true }).click();

		const column_maps = page.locator(".diw-col-map-field input");
		await expect(column_maps.first()).toHaveValue("ID");
		await expect(column_maps.nth(1)).toHaveValue("First Name");
	});
});
