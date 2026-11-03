import fs from "fs";
import { test, expect } from "../support";
import { drop_file } from "../support/drop_file";

const HEADER = "Number (phone),Is Primary Phone (is_primary_phone)";
const PARSE_FILE = "/api/method/frappe.desk.form.grid_import.parse_file";

test.describe("Child Table Data Import", () => {
	let contact;

	test.beforeAll(async ({ admin }) => {
		const doc = await admin.insert_doc("Contact", {
			first_name: "Grid Import",
			phone_nos: Array.from({ length: 5 }, (_, i) => ({ phone: `+91-90000000${i}` })),
		});
		contact = doc.name;
	});

	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("Contact", contact, true);
	});

	test.beforeEach(async ({ page }) => {
		await page.goto(`/desk/contact/${contact}`);
		await page.waitForFunction(
			(name) => window.cur_frm?.doc.name === name && cur_frm.get_field("phone_nos"),
			contact
		);
		await page.evaluate(() => {
			cur_frm.get_docfield("phone_nos").allow_bulk_edit = 1;
			cur_frm.get_field("phone_nos").grid.setup_allow_bulk_edit();
		});
	});

	const dialog = (page) => page.locator(".grid-import-dialog:visible");
	const hint = (page) => dialog(page).locator(".grid-import-preview-hint");
	const primary_button = (page) => dialog(page).locator(".standard-actions .btn-modal-primary");

	const phone_rows = (page) =>
		page.evaluate(() =>
			cur_frm.doc.phone_nos.map(({ name, phone, is_primary_phone }) => ({
				name,
				phone,
				is_primary_phone,
			}))
		);

	const click_primary = async (page, label) => {
		const button = primary_button(page);
		await expect(button).toContainText(label);
		await expect(button).toBeEnabled();
		await button.click();
	};

	const open_import = async (page, import_type = "Insert New Records") => {
		await page.locator('.frappe-control[data-fieldname="phone_nos"] .grid-upload').click();
		await dialog(page)
			.locator('select[data-fieldname="import_type"]')
			.selectOption(import_type);
	};

	const upload = async (page, rows, header = HEADER) => {
		const file = test.info().outputPath("phone_nos.csv");
		fs.writeFileSync(file, [header, ...rows].join("\n"));
		await drop_file(dialog(page).locator(".file-upload-area"), file, "text/csv");

		const parsed = page.waitForResponse((res) => res.url().includes(PARSE_FILE));
		await click_primary(page, "Next");
		await parsed;
		await expect(dialog(page).locator(".modal-title")).not.toContainText("Upload");
	};

	const skip_all = (page) => dialog(page).locator("thead .grid-import-skip-cell input").check();

	test("adds imported rows alongside the existing ones", async ({ page }) => {
		const before = await phone_rows(page);
		await open_import(page);
		await upload(page, ["9876500001,0", "9876500002,1"]);
		await click_primary(page, "Upload");
		await expect(page.getByText("2 added, 0 skipped, save to apply")).toBeVisible();

		const numbers = (await phone_rows(page)).map((row) => row.phone);
		expect(numbers).toHaveLength(before.length + 2);
		expect(numbers).toEqual(expect.arrayContaining(["9876500001", "9876500002"]));
	});

	test("stops on Fix Issues until the bad cell is fixed", async ({ page }) => {
		await open_import(page);
		await upload(page, ["9876500003,maybe", "9876500004,0"]);

		await expect(primary_button(page)).toBeDisabled();
		await dialog(page).locator('td[data-col="1"].has-error select').selectOption("1");
		await expect(dialog(page).locator("td.has-error")).toHaveCount(0);
		await expect(primary_button(page)).toBeEnabled();
	});

	test("lets a bad row be skipped instead of fixed", async ({ page }) => {
		const before = await phone_rows(page);
		await open_import(page);
		await upload(page, ["9876500005,maybe", "9876500006,0"]);

		await skip_all(page);
		await click_primary(page, "Next");
		await click_primary(page, "Upload");
		await expect(page.getByText("1 added, 1 skipped, save to apply")).toBeVisible();

		const numbers = (await phone_rows(page)).map((row) => row.phone);
		expect(numbers).toHaveLength(before.length + 1);
		expect(numbers).toContain("9876500006");
		expect(numbers).not.toContain("9876500005");
	});

	test("updates the row matching the ID and flags blank or unmatched IDs", async ({ page }) => {
		const [first] = await phone_rows(page);
		await open_import(page, "Update Existing Records");
		await upload(
			page,
			[`${first.name},9876500010,1`, "no-such-row,9876500011,0", ",9876500012,0"],
			`ID,${HEADER}`
		);

		const id_input = (row) =>
			dialog(page).locator(`tr[data-row="${row}"] td[data-col="0"].has-error input`);
		const message = dialog(page).locator(".grid-import-footer-message");
		await expect(primary_button(page)).toBeDisabled();
		await id_input(3).click();
		await expect(message).toContainText('No row in this table has the ID "no-such-row".');
		await id_input(4).click();
		await expect(message).toContainText("This field is mandatory and is blank.");

		await skip_all(page);
		await click_primary(page, "Next");
		await click_primary(page, "Upload");
		await expect(page.getByText("1 updated, 2 skipped, save to apply")).toBeVisible();

		const rows = await phone_rows(page);
		expect(rows.find((row) => row.name === first.name)).toMatchObject({
			phone: "9876500010",
			is_primary_phone: 1,
		});
		expect(rows.map((row) => row.phone)).not.toContain("9876500011");
	});

	test("does not count unchanged rows as updated", async ({ page }) => {
		const [first] = await phone_rows(page);
		await open_import(page, "Update Existing Records");
		await upload(
			page,
			[`${first.name},9876500020`, `${first.name},${first.phone}`],
			"ID,Number (phone)"
		);

		await expect(hint(page)).toContainText("0 rows will be updated.");
		await click_primary(page, "Upload");
		await expect(page.getByText("0 updated, 0 skipped, save to apply")).toBeVisible();
	});

	test("upserts: updates known IDs and adds the rest", async ({ page }) => {
		const [first] = await phone_rows(page);
		await open_import(page, "Insert or Update Records");
		await upload(page, [`${first.name},9876500030,0`, ",9876500031,0"], `ID,${HEADER}`);

		await expect(hint(page)).toContainText("1 row will be inserted and 1 updated.");
		await click_primary(page, "Upload");
		await expect(page.getByText("1 added, 1 updated, 0 skipped, save to apply")).toBeVisible();

		const rows = await phone_rows(page);
		expect(rows.find((row) => row.name === first.name).phone).toBe("9876500030");
		expect(rows.map((row) => row.phone)).toContain("9876500031");
	});

	test("blocks an insert when a mandatory field has no column", async ({ page }) => {
		await open_import(page);
		await upload(page, ["1"], "Is Primary Phone (is_primary_phone)");

		await expect(hint(page)).toContainText(
			"In Contact Numbers, Number is required in every row."
		);
		await expect(primary_button(page)).toBeDisabled();
	});

	test("does not let two columns fill the same field", async ({ page }) => {
		await open_import(page);
		await upload(page, ["9876500040,9876500041"], "Number (phone),Number");

		await expect(hint(page)).toContainText("Two columns map to the same field");
		await expect(dialog(page).locator(".grid-import-mapping-row td.has-error")).toHaveCount(2);
		await expect(primary_button(page)).toBeDisabled();
	});

	test("skips to Preview when more than 50 rows need fixing", async ({ page }) => {
		await open_import(page);
		await upload(page, [
			"9876501100,0",
			"9876501101,0",
			...Array.from({ length: 60 }, (_, i) => `98765${1200 + i},maybe`),
		]);

		const alert = dialog(page).locator(".grid-import-preview-alert .es-alert");
		await expect(alert).toContainText("Too Many Errors");
		await expect(alert).toContainText("60 of 62 uploaded rows need fixing");
		await expect(dialog(page).locator(".grid-import-preview-table")).toBeHidden();

		await click_primary(page, "Skip Invalid and Continue");
		await expect(hint(page)).toContainText("2 rows will be inserted.");
		await expect(dialog(page).locator(".grid-import-skip-cell")).toHaveCount(0);
	});
});

test.describe("Child Table Data Export", () => {
	const doctype = "Grid Export Doctype";
	const child_doctype = {
		doctype: "DocType",
		name: "Grid Export Item",
		module: "Custom",
		custom: 1,
		istable: 1,
		fields: [
			{ fieldname: "item_name", fieldtype: "Data", label: "Item Name", reqd: 1 },
			{ fieldname: "qty", fieldtype: "Int", label: "Qty" },
			{ fieldname: "rate", fieldtype: "Currency", label: "Rate", permlevel: 1 },
			{
				fieldname: "internal_note",
				fieldtype: "Data",
				label: "Internal Note",
				permlevel: 2,
			},
		],
	};
	const parent_doctype = {
		doctype: "DocType",
		name: doctype,
		module: "Custom",
		custom: 1,
		is_submittable: 1,
		fields: [
			{ fieldname: "title", fieldtype: "Data", label: "Title" },
			{
				fieldname: "items",
				fieldtype: "Table",
				label: "Items",
				options: child_doctype.name,
				allow_bulk_edit: 1,
			},
		],
		permissions: [
			{
				role: "System Manager",
				read: 1,
				write: 1,
				create: 1,
				delete: 1,
				submit: 1,
				cancel: 1,
			},
			{ role: "System Manager", permlevel: 1, read: 1, write: 0 },
		],
	};
	const items = [
		{ item_name: "Bolt", qty: 4, rate: 12.5, internal_note: "fragile" },
		{ item_name: "Nut", qty: 9, rate: 3, internal_note: "spare" },
	];
	let submitted;
	let draft;

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", child_doctype, true);
		await admin.insert_doc("DocType", parent_doctype, true);
		submitted = (await admin.insert_doc(doctype, { title: "Submitted", items, docstatus: 1 }))
			.name;
		draft = (await admin.insert_doc(doctype, { title: "Draft", items })).name;
	});

	test.afterAll(async ({ admin }) => {
		await admin.call("frappe.client.cancel", { doctype, name: submitted });
		await admin.remove_doc(doctype, submitted, true);
		await admin.remove_doc(doctype, draft, true);
	});

	const open_form = async (page, name) => {
		await page.goto(`/desk/grid-export-doctype/${name}`);
		await page.waitForFunction(
			(name) => window.cur_frm?.doc.name === name && cur_frm.get_field("items"),
			name
		);
		return page.locator('.frappe-control[data-fieldname="items"]');
	};

	const export_dialog = (page) =>
		page.locator(".modal:visible").filter({ hasText: "Export Data" }).last();
	const field_option = (exporter, label) =>
		exporter.locator(".unit-checkbox").filter({ hasText: label });

	const read_csv = async (download) =>
		fs
			.readFileSync(await download.path(), "utf8")
			.trim()
			.split(/\r?\n/)
			.map((line) => line.split(",").map((value) => value.replace(/^"|"$/g, "")));

	test("downloads every row of a submitted document with the readable fields", async ({
		page,
	}) => {
		const grid = await open_form(page, submitted);
		await expect(grid.locator(".grid-upload")).toBeHidden();
		await grid.locator(".grid-download").click();

		const exporter = export_dialog(page);
		await expect(exporter).not.toContainText("Select Fields To");
		await expect(exporter.locator('select[data-fieldname="export_records"]')).toHaveValue(
			"all"
		);
		await expect(field_option(exporter, "Rate").locator("input")).toBeChecked();
		await expect(field_option(exporter, "Internal Note")).toHaveCount(0);
		await expect(exporter.locator(".unit-checkbox input:not(:checked)")).toHaveCount(0);

		const download = page.waitForEvent("download");
		await exporter.locator(".btn-modal-primary").click();
		const names = await page.evaluate(() => cur_frm.doc.items.map((row) => row.name));
		expect(await read_csv(await download)).toEqual([
			["ID", "Item Name (item_name)", "Qty (qty)", "Rate (rate)"],
			[names[0], "Bolt", "4", "12.5"],
			[names[1], "Nut", "9", "3"],
		]);
	});

	test("keeps Upload and the import template on a draft document", async ({ page }) => {
		const grid = await open_form(page, draft);
		await expect(grid.locator(".grid-download")).toBeHidden();
		await grid.locator(".grid-upload").click();
		await page
			.locator(".grid-import-dialog:visible")
			.getByRole("button", { name: "Download Template" })
			.click();

		const exporter = export_dialog(page);
		await expect(exporter).toContainText("Select Fields To Insert");
		await expect(exporter.locator('select[data-fieldname="export_records"]')).toHaveValue(
			"blank_template"
		);
		await expect(field_option(exporter, "Item Name")).toHaveCount(1);
		await expect(field_option(exporter, "Rate")).toHaveCount(0);
	});
});
