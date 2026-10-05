import { test, expect } from "../support";

const PRINT_FORMAT_API = "api/method/frappe.printing.doctype.print_format.print_format";

let PF_NAME;
const created_formats = new Set();
const created_letter_heads = new Set();

test.beforeEach(() => {
	PF_NAME = track(pf_name());
});

// deleting a format queues a background job that writes to the site, so the formats
// are removed once at the end instead of between tests where that job would race the
// next test's setup
test.afterAll(async ({ admin }) => {
	for (const name of created_formats) {
		await admin.remove_doc("Print Format", name, true);
	}
	for (const name of created_letter_heads) {
		await admin.remove_doc("Letter Head", name, true);
	}
});

function pf_name() {
	return `Playwright PF ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

function track(name) {
	created_formats.add(name);
	return name;
}

function builder_layout(sections = []) {
	return {
		sections,
		header: { columns: [{ label: "", fields: [] }] },
		footer: { columns: [{ label: "", fields: [] }] },
	};
}

function one_section_layout() {
	return JSON.stringify(
		builder_layout([{ label: "Alpha", columns: [{ label: "", fields: [] }] }])
	);
}

function insert_contact_table_format(api, name) {
	return api.insert_doc(
		"Print Format",
		{
			name,
			doc_type: "Contact",
			print_format_builder_beta: 1,
			format_data: JSON.stringify(
				builder_layout([
					{
						label: "Rep Section",
						columns: [
							{
								label: "",
								fields: [
									{
										fieldtype: "Repeater",
										fieldname: "rep1",
										label: "Rep",
										source: "email_ids",
										repeater_columns: [{ template: [], align: "left" }],
									},
								],
							},
						],
					},
				])
			),
		},
		true
	);
}

function insert_builder_format(api, name, sections = []) {
	return api.insert_doc(
		"Print Format",
		{
			name,
			doc_type: "ToDo",
			print_format_builder_beta: 1,
			format_data: JSON.stringify(builder_layout(sections)),
		},
		true
	);
}

async function open_builder(page, name) {
	await page.goto(`/desk/print-format-builder/${encodeURIComponent(name)}`);
	await builder_loaded(page);
}

// the tail of the initial load re-renders the inspector and resets the dirty flag, so
// an edit made before the load settles is lost
function builder_loaded(page) {
	return page.waitForFunction(() => {
		const store = window.frappe?.print_format_builder?.$component?.$store;
		return store?.layout.value && !store.dirty.value && frappe.request.ajax_count === 0;
	});
}

function wait_for_call(page, method) {
	return page.waitForResponse(
		(res) =>
			res.request().method() === "POST" &&
			res.url().includes(`${PRINT_FORMAT_API}.${method}`)
	);
}

async function save_and_apply(page) {
	const applied = wait_for_call(page, "apply_draft");
	await page
		.locator(".page-actions .primary-action:visible", { hasText: "Save & Apply" })
		.first()
		.click();
	const response = await applied;
	expect(response.status()).toBe(200);
	return (await response.json()).message;
}

function section(page, label) {
	return page.locator("[data-pfb-section]", { hasText: label }).first();
}

function tree_row(page, label) {
	return page.locator(".pfb-tree-row", { hasText: label }).first();
}

function closest(locator, class_name) {
	return locator.locator(
		`xpath=ancestor::*[contains(concat(" ", normalize-space(@class), " "), " ${class_name} ")][1]`
	);
}

async function set_input(input, value) {
	await input.fill(value);
	await input.dispatchEvent("change");
	await input.blur();
}

async function wait_for_canvas(page) {
	// the canvas re-lays out once the sample document arrives, which moves the drag handles
	await expect(
		page.locator(".canvas-toolbar-hint, .sections-container .field--preview").first()
	).toBeVisible();
	await page.waitForFunction(() => frappe.request.ajax_count === 0);
}

async function drag(page, handle, dx, dy = 0) {
	// selecting a section smooth-scrolls the canvas; hover waits for the handle to settle
	await handle.hover();
	const box = await handle.boundingBox();
	const x = box.x + box.width / 2;
	const y = box.y + box.height / 2;
	await page.mouse.down();
	await page.mouse.move(Math.max(0, x + dx), Math.max(0, y + dy), { steps: 5 });
	await page.mouse.up();
}

function css_number(locator, property) {
	return locator.evaluate(
		(el, property) => parseInt(getComputedStyle(el).getPropertyValue(property), 10),
		property
	);
}

function expect_within(value, min, max) {
	expect(value).toBeGreaterThanOrEqual(min);
	expect(value).toBeLessThanOrEqual(max);
}

async function get_format_values(api, name, fieldname) {
	const r = await api.call("frappe.client.get_value", {
		doctype: "Print Format",
		filters: { name },
		fieldname,
	});
	return r.message;
}

async function open_new_format_dialog(page, desk) {
	await page.goto("/desk/print-format");
	await page.locator(".page-head:visible .primary-action").click();
	const dialog = desk.get_open_dialog();
	await expect(dialog).toContainText("New Print Format");
	// the dialog focuses its first field once shown, which would steal later keystrokes
	await expect(dialog.locator('[data-fieldname="print_format_for"] select')).toBeFocused();
	return dialog;
}

function committed_value(page, fieldname) {
	return page.evaluate((fieldname) => cur_dialog.get_field(fieldname).value, fieldname);
}

async function fill_new_format_dialog(page, dialog, name) {
	await fill_dialog_link(dialog, "doc_type", "ToDo");
	await expect.poll(() => committed_value(page, "doc_type")).toBe("ToDo");

	// the dialog refreshes its fields a moment after any change, which resets an input
	// that has not been committed yet, so fill again until the name sticks
	const name_input = dialog.locator('[data-fieldname="print_format_name"] input:visible');
	await expect(async () => {
		await name_input.fill(name);
		await name_input.blur();
		expect(await committed_value(page, "print_format_name")).toBe(name);
	}).toPass({ timeout: 20000 });
}

// a Repeater drops the .field class once a sample document loads into the canvas
function repeater_field(page) {
	return section(page, "Rep Section").locator(".field, .pfb-repeater").first();
}

async function fill_dialog_link(dialog, fieldname, value) {
	const input = dialog.locator(`[data-fieldname="${fieldname}"] input:visible`).first();
	const dropdown = input.locator("xpath=..").getByRole("listbox");
	await input.clear();
	await input.focus();
	await expect(dropdown).toBeVisible();
	await input.pressSequentially(value, { delay: 100 });
	await expect(dropdown.locator("div[role='option']").first()).toContainText(value);
	await input.press("Enter");
	await input.blur();
	await expect(dropdown).toHaveCount(0);
	await expect(input).toHaveValue(value);
}

test.describe("Print Format Builder — create flow", () => {
	test("redirects to the Print Format list when opened without a format", async ({ page }) => {
		await page.goto("/desk/print-format-builder");
		await expect(page).toHaveURL((url) =>
			/^\/(app|desk)\/(?:[\w-]+\/)?print-format(\/view\/list)?$/.test(url.pathname)
		);
	});

	test("opens the builder from the Print Format form", async ({ page, api }) => {
		await insert_builder_format(api, PF_NAME);

		await page.goto(`/desk/print-format/${encodeURIComponent(PF_NAME)}`);
		await page
			.locator(".page-actions:visible button", { hasText: "Edit Format" })
			.first()
			.click();

		await expect(page).toHaveURL((url) =>
			/\/(app|desk)\/(?:[\w-]+\/)?print-format-builder\//.test(url.pathname)
		);
		await expect(page.locator(".print-format-main")).toBeAttached();
	});

	test("creates an HTML format from the dialog and opens the form", async ({
		page,
		desk,
		api,
	}) => {
		const dialog = await open_new_format_dialog(page, desk);

		await fill_new_format_dialog(page, dialog, PF_NAME);
		await dialog.locator('[data-fieldname="start_with"] select:visible').selectOption("HTML");
		await dialog.getByRole("button", { name: "Create", exact: true }).click();

		await expect(page).toHaveURL((url) =>
			/\/(app|desk)\/(?:[\w-]+\/)?print-format\/(?!view\/)/.test(url.pathname)
		);
		const created = decodeURIComponent(new URL(page.url()).pathname.split("/").pop());
		expect(created).toContain(PF_NAME.split(" ").pop());
		track(created);

		const values = await get_format_values(api, created, [
			"custom_format",
			"print_format_builder_beta",
			"html",
		]);
		expect(Number(values.custom_format)).toBe(1);
		expect(Number(values.print_format_builder_beta)).toBe(0);
		expect(values.html).toContain("print-format");
	});

	test("creates a builder format from the dialog and opens the builder", async ({
		page,
		desk,
		api,
	}) => {
		const dialog = await open_new_format_dialog(page, desk);

		await fill_new_format_dialog(page, dialog, PF_NAME);
		await dialog.getByRole("button", { name: "Create", exact: true }).click();

		await expect(page).toHaveURL((url) =>
			/\/(app|desk)\/(?:[\w-]+\/)?print-format-builder\//.test(url.pathname)
		);
		const created = decodeURIComponent(new URL(page.url()).pathname.split("/").pop());
		expect(created).toContain(PF_NAME.split(" ").pop());
		track(created);

		const values = await get_format_values(api, created, [
			"custom_format",
			"print_format_builder_beta",
		]);
		expect(Number(values.custom_format)).toBe(0);
		expect(Number(values.print_format_builder_beta)).toBe(1);
	});

	test("left panel opens on Fields and remembers the tab you left on", async ({ page, api }) => {
		await insert_builder_format(api, PF_NAME, [
			{ label: "Alpha", columns: [{ label: "", fields: [] }] },
		]);
		await open_builder(page, PF_NAME);

		const tabs = page.locator(".es-tabs__tab");
		await expect(tabs).toHaveCount(4);
		expect(await tabs.evaluateAll((els) => els.map((el) => el.dataset.tab))).toEqual([
			"fields",
			"layers",
			"blocks",
			"library",
		]);

		await page.evaluate(() => localStorage.removeItem("pfb_active_tab"));
		await page.reload();
		await expect(page.locator(".es-tabs__tab[data-tab='fields']")).toHaveAttribute(
			"data-state",
			"active"
		);

		await page.locator(".es-tabs__tab[data-tab='blocks']").click();
		await page.reload();
		await expect(page.locator(".es-tabs__tab[data-tab='blocks']")).toHaveAttribute(
			"data-state",
			"active"
		);
	});

	test("layers tab selects a section on click", async ({ page, api }) => {
		await insert_builder_format(api, PF_NAME, [
			{ label: "Alpha", columns: [{ label: "", fields: [] }] },
			{ label: "Beta", columns: [{ label: "", fields: [] }] },
		]);

		await open_builder(page, PF_NAME);

		await page.locator(".es-tabs__tab[data-tab='layers']").click();
		await tree_row(page, "Beta").click();

		await expect(page.locator(".pfb-inspector")).toContainText("Section");
		await expect(page.locator(".pfb-inspector")).toContainText("Beta");
		await expect(tree_row(page, "Beta")).toHaveClass(/(^|\s)active(\s|$)/);
	});

	test("field breadcrumb navigates to parent section", async ({ page, api }) => {
		await insert_builder_format(api, PF_NAME, [
			{
				label: "Details",
				columns: [
					{
						label: "",
						fields: [
							{ fieldtype: "Data", fieldname: "description", label: "Description" },
						],
					},
				],
			},
		]);

		await open_builder(page, PF_NAME);

		await page.locator(".es-tabs__tab[data-tab='layers']").click();
		await tree_row(page, "Details").click();

		await page.locator(".print-format-container").click();
		await section(page, "Details").locator(".field").first().click();

		await expect(page.locator(".pfb-breadcrumb")).toBeVisible();
		await expect(page.locator(".pfb-breadcrumb-name")).toContainText("Details");

		await page.locator(".pfb-breadcrumb-btn").click();
		await expect(page.locator(".pfb-inspector")).toContainText("Section");
		await expect(page.locator(".pfb-inspector")).toContainText("Details");
		await expect(page.locator(".pfb-breadcrumb")).toHaveCount(0);
	});

	test("font size change applies to canvas preview", async ({ page, api }) => {
		await insert_builder_format(api, PF_NAME, []);

		await open_builder(page, PF_NAME);

		await expect(page.locator(".pfb-margin-grid")).toBeVisible();

		const label = page.locator("label", { hasText: "Font Size" }).first();
		await set_input(closest(label, "form-group").locator("input"), "18");

		await expect.poll(() => css_number(page.locator(".pfb-body"), "font-size")).toBe(18);
	});

	test("settings label color persists on save", async ({ page, api }) => {
		await insert_builder_format(api, PF_NAME, []);

		await open_builder(page, PF_NAME);

		await expect(page.locator(".pfb-margin-grid")).toBeVisible();

		await expect(
			page.locator('[data-fieldname="label_color"] .selected-color')
		).toBeAttached();

		await set_input(page.locator('[data-fieldname="label_color"] input:visible'), "#c0392b");

		const saved = await save_and_apply(page);
		expect(saved.label_color).toBe("#c0392b");
	});

	test("picking Image shows image controls for an HTML-only letter head", async ({
		page,
		api,
	}) => {
		const letter_head = `Playwright LH ${Date.now()}`;
		created_letter_heads.add(letter_head);
		await api.insert_doc(
			"Letter Head",
			{ letter_head_name: letter_head, source: "Image", content: "<p>Acme Header</p>" },
			true
		);
		await api.insert_doc(
			"Print Format",
			{
				name: PF_NAME,
				doc_type: "ToDo",
				print_format_builder_beta: 1,
				format_data: JSON.stringify({ ...builder_layout(), letter_head }),
			},
			true
		);

		await open_builder(page, PF_NAME);
		await page.locator(".lh-zone").first().click();

		const inspector = page.locator(".pfb-inspector");
		const source = (label) => inspector.locator(".es-pill", { hasText: label }).first();
		await expect(inspector).toContainText("Edit HTML");

		await source("Image").click();
		await expect(inspector).toContainText("Upload Image");
		await expect(inspector).not.toContainText("Edit HTML");

		await source("HTML").click();
		await expect(inspector).toContainText("Edit HTML");
	});

	test("custom table column settings open from the row", async ({ page, api }) => {
		await insert_contact_table_format(api, PF_NAME);

		await open_builder(page, PF_NAME);
		await expect(page.locator("[data-pfb-section]").first()).toBeVisible();
		await repeater_field(page).click();

		const inspector = page.locator(".pfb-inspector");
		await expect(inspector).toContainText("Custom Table");
		await expect(inspector).toContainText("Columns");
		await expect(inspector.locator(".pfb-col-row")).toHaveCount(1);
		await expect(inspector.locator(".pfb-col-editor")).toHaveCount(0);
		await inspector.locator(".pfb-col-row button[title='Column settings']").click();
		await expect(inspector.locator(".pfb-col-editor")).toContainText("Width");
		await expect(inspector.locator(".pfb-col-editor")).toContainText("Align");
		await expect(inspector.locator(".pfb-col-editor")).toContainText("Colour");
	});

	test("slash in a custom table column inserts a field chip", async ({ page, api }) => {
		await insert_contact_table_format(api, PF_NAME);

		await open_builder(page, PF_NAME);
		await expect(page.locator("[data-pfb-section]").first()).toBeVisible();
		await repeater_field(page).click();

		const template = page.locator(".pfb-inspector .pfb-col-row .pfb-tpl-text").first();
		await template.pressSequentially("Mail: /ema");
		await expect(page.locator(".pfb-tpl-menu")).toContainText("Email");
		await template.press("Enter");
		await expect(page.locator(".pfb-tpl-menu")).toHaveCount(0);
		await expect(
			page.locator(".pfb-inspector .pfb-col-row .es-badge", { hasText: "Email" }).first()
		).toBeVisible();
		await expect(template).toHaveValue("Mail: ");
	});

	test("field inspector header keeps the doctype label after a custom rename", async ({
		page,
		api,
	}) => {
		await insert_builder_format(api, PF_NAME, [
			{
				label: "Details",
				columns: [
					{
						label: "",
						fields: [{ fieldtype: "Date", fieldname: "date", label: "Deadline" }],
					},
				],
			},
		]);

		await open_builder(page, PF_NAME);

		await expect(page.locator("[data-pfb-section]").first()).toBeVisible();
		await section(page, "Details").locator(".field").first().click();

		await expect(page.locator(".pfb-inspector")).toContainText("Due Date");
		await expect(page.locator(".pfb-inspector")).not.toContainText("Deadline");
		await expect(
			page
				.locator(".pfb-insp-row", { hasText: "Label" })
				.first()
				.locator("input.pfb-insp-input")
		).toHaveValue("Deadline");
	});

	test("field align overrides a conflicting label-justify setting", async ({ page, api }) => {
		// the left-right/align classes only render in live preview mode, so
		// the doctype needs at least one record to auto-preview
		await api.insert_doc("ToDo", { description: "pfb align override preview" }, true);

		await insert_builder_format(api, PF_NAME, [
			{
				label: "Details",
				field_orientation: "left-right",
				columns: [
					{
						label: "",
						fields: [
							{
								fieldtype: "Date",
								fieldname: "date",
								label: "Due Date",
								align: "center",
								label_justify: "space-between",
							},
						],
					},
				],
			},
		]);

		await open_builder(page, PF_NAME);

		await expect(page.locator("[data-pfb-section]").first()).toBeVisible();
		const field = section(page, "Details").locator(".field.left-right");
		await field.click();

		await expect(field).toHaveCSS("justify-content", "center");
		await expect(page.locator(".pfb-inspector")).not.toContainText("Spacing");
	});
});

test.describe("Print Format Builder — setup flow", () => {
	test("skips setup screen when a layout is already saved", async ({ page, api }) => {
		await api.insert_doc(
			"Print Format",
			{
				name: PF_NAME,
				doc_type: "ToDo",
				print_format_builder_beta: 1,
				format_data: one_section_layout(),
			},
			true
		);

		await open_builder(page, PF_NAME);

		await expect(page.locator(".sections-container")).toBeVisible();
		await expect(page.locator(".pfb-setup")).toHaveCount(0);
	});

	test("Start blank dismisses setup and shows empty canvas", async ({ page, api }) => {
		await api.insert_doc(
			"Print Format",
			{ name: PF_NAME, doc_type: "ToDo", print_format_builder_beta: 1 },
			true
		);

		await open_builder(page, PF_NAME);

		await expect(page.locator(".pfb-setup")).toBeVisible();
		await page.locator(".pfb-setup-option-label", { hasText: "Start blank" }).first().click();

		await expect(page.locator(".pfb-setup")).toHaveCount(0);
		await expect(page.locator(".body-empty")).toBeVisible();
		await expect(page.locator(".sections-container [data-pfb-section]")).toHaveCount(0);

		const saved = await save_and_apply(page);
		expect(JSON.parse(saved.format_data).sections).toEqual([]);
	});

	test("Start from default dismisses setup and fills canvas with document fields", async ({
		page,
		api,
	}) => {
		await api.insert_doc(
			"Print Format",
			{ name: PF_NAME, doc_type: "ToDo", print_format_builder_beta: 1 },
			true
		);

		await open_builder(page, PF_NAME);

		await expect(page.locator(".pfb-setup")).toBeVisible();
		await page
			.locator(".pfb-setup-option-label", { hasText: "Start from default" })
			.first()
			.click();

		await expect(page.locator(".pfb-setup")).toHaveCount(0);
		await expect(page.locator(".sections-container [data-pfb-section]")).not.toHaveCount(0);

		const saved = await save_and_apply(page);
		expect(JSON.parse(saved.format_data).sections.length).toBeGreaterThan(0);
	});
});

test.describe("Print Format Builder — section insert", () => {
	test("clicking section insert before a section inserts a new section", async ({
		page,
		api,
	}) => {
		await api.insert_doc(
			"Print Format",
			{
				name: PF_NAME,
				doc_type: "ToDo",
				print_format_builder_beta: 1,
				format_data: one_section_layout(),
			},
			true
		);

		await open_builder(page, PF_NAME);
		const sections = page.locator(".sections-container [data-pfb-section]");
		await expect(sections).toHaveCount(1);

		await page.locator(".section-with-insert .section-insert-btn").first().click();

		await expect(sections).toHaveCount(2);
	});

	test("inserting sections three times yields three sections on a blank canvas", async ({
		page,
		api,
	}) => {
		await api.insert_doc(
			"Print Format",
			{
				name: PF_NAME,
				doc_type: "ToDo",
				print_format_builder_beta: 1,
				format_data: JSON.stringify({
					sections: [],
					header: { columns: [{ label: "", fields: [] }] },
					footer: { columns: [{ label: "", fields: [] }] },
				}),
			},
			true
		);

		await open_builder(page, PF_NAME);
		const sections = page.locator(".sections-container [data-pfb-section]");
		await expect(page.locator(".body-empty")).toBeVisible();
		await expect(sections).toHaveCount(0);

		await page.locator(".body-empty").click();
		await expect(sections).toHaveCount(1);

		const insert_at_end = page.locator(
			".sections-container > .section-insert .section-insert-btn"
		);
		await insert_at_end.click();
		await expect(sections).toHaveCount(2);

		await insert_at_end.click();
		await expect(sections).toHaveCount(3);
	});
});

test.describe("Print Format Builder — column width resize", () => {
	function two_column_section() {
		return [
			{
				label: "Two Cols",
				columns: [
					{
						label: "",
						fields: [
							{ fieldtype: "Data", fieldname: "description", label: "Description" },
						],
					},
					{
						label: "",
						fields: [{ fieldtype: "Data", fieldname: "status", label: "Status" }],
					},
				],
			},
		];
	}

	test("dragging the section column handle resizes and persists widths", async ({
		page,
		api,
	}) => {
		await insert_builder_format(api, PF_NAME, two_column_section());

		await open_builder(page, PF_NAME);
		await expect(page.locator(".sections-container")).toBeVisible();
		await wait_for_canvas(page);

		const columns = page.locator(".sections-container .column");
		await expect(columns.first()).not.toHaveAttribute("style");

		const total = (
			await page.locator(".sections-container .section-columns").first().boundingBox()
		).width;
		await drag(
			page,
			page.locator(".sections-container .col-width-handle").first(),
			-total * 0.2
		);

		await expect(async () => {
			expect_within(await css_number(columns.first(), "flex-grow"), 25, 35);
			expect_within(await css_number(columns.nth(1), "flex-grow"), 65, 75);
		}).toPass({ timeout: 20000 });

		const saved = await save_and_apply(page);
		const cols = JSON.parse(saved.format_data).sections[0].columns;
		// the container gap is excluded from measured widths and each width
		// is rounded, so the sum lands a few points under 100
		expect_within(cols[0].width, 23, 38);
		expect_within(cols[1].width, 60, 77);
		expect_within(cols[0].width + cols[1].width, 88, 100);

		await drag(page, page.locator(".sections-container .col-width-handle").first(), -5000);
		await expect
			.poll(() => css_number(columns.first(), "flex-grow"), "clamps at the 10% minimum")
			.toBeGreaterThanOrEqual(10);
	});

	test("dragging the table column handle resizes and persists widths", async ({ page, api }) => {
		// table markup (and its resize handles) only renders in live preview
		// mode, so the doctype needs at least one record to auto-preview
		await api.insert_doc("ToDo", { description: "pfb column resize preview" }, true);

		await insert_builder_format(api, PF_NAME, [
			{
				label: "Tbl",
				columns: [
					{
						label: "",
						fields: [
							{
								fieldtype: "Table",
								fieldname: "assignments_cy1",
								label: "Items",
								custom: 1,
								table_columns: [
									{
										fieldname: "a",
										label: "Alpha",
										fieldtype: "Data",
										width: 50,
									},
									{
										fieldname: "b",
										label: "Beta",
										fieldtype: "Data",
										width: 50,
									},
								],
							},
						],
					},
				],
			},
		]);

		await open_builder(page, PF_NAME);
		await expect(page.locator(".sections-container")).toBeVisible();

		await expect(page.locator(".sections-container th.column-header")).toHaveCount(2);
		await expect(page.locator(".sections-container .col-resize-handle")).toHaveCount(1);
		await wait_for_canvas(page);

		const total = (await page.locator(".sections-container table.table").first().boundingBox())
			.width;
		await drag(
			page,
			page.locator(".sections-container .col-resize-handle").first(),
			-total * 0.2
		);

		const saved = await save_and_apply(page);
		const fields = JSON.parse(saved.format_data)
			.sections.flatMap((s) => s.columns)
			.flatMap((c) => c.fields);
		const table = fields.find((f) => f.fieldtype === "Table");
		expect(table, "table field survived").toBeTruthy();
		expect_within(table.table_columns[0].width, 25, 35);
		expect_within(table.table_columns[1].width, 65, 75);
		expect(table.table_columns[0].width + table.table_columns[1].width).toBe(100);
	});
});

test.describe("Print Format Builder — image and barcode blocks", () => {
	test("image and barcode props survive the save round-trip", async ({ page, api }) => {
		await insert_builder_format(api, PF_NAME, [
			{
				label: "Media",
				columns: [
					{
						label: "",
						fields: [
							{
								fieldtype: "Image",
								fieldname: "image_cy1",
								label: "Logo",
								custom: 1,
								image_url: "/assets/frappe/images/frappe-framework-logo.svg",
								width: "40mm",
								align: "center",
							},
							{
								fieldtype: "Barcode",
								fieldname: "barcode_cy1",
								label: "",
								custom: 1,
								barcode_value: "CY-TEST-1",
								barcode_format: "CODE128",
								show_text: true,
								width: "200px",
							},
						],
					},
				],
			},
		]);

		await open_builder(page, PF_NAME);
		await expect(page.locator(".sections-container")).toBeVisible();

		await expect(page.locator('.field img[src*="frappe-framework-logo"]')).toBeAttached();

		const saved = await save_and_apply(page);
		const fields = JSON.parse(saved.format_data)
			.sections.flatMap((s) => s.columns)
			.flatMap((c) => c.fields);

		const img = fields.find((f) => f.fieldtype === "Image");
		expect(img, "image field survived").toBeTruthy();
		expect(img).toMatchObject({
			custom: 1,
			image_url: "/assets/frappe/images/frappe-framework-logo.svg",
			width: "40mm",
			align: "center",
		});

		const bar = fields.find((f) => f.fieldtype === "Barcode");
		expect(bar, "barcode field survived").toBeTruthy();
		expect(bar).toMatchObject({
			custom: 1,
			barcode_value: "CY-TEST-1",
			barcode_format: "CODE128",
			show_text: true,
			width: "200px",
		});
	});
});

test.describe("Print Format Builder — selection & spacing", () => {
	function three_field_format(api, name) {
		return insert_builder_format(api, name, [
			{
				label: "Alpha",
				columns: [
					{
						label: "",
						fields: [
							{ fieldtype: "Data", fieldname: "description", label: "Description" },
							{ fieldtype: "Data", fieldname: "status", label: "Status" },
							{ fieldtype: "Data", fieldname: "priority", label: "Priority" },
						],
					},
				],
			},
		]);
	}

	test("shift-click selects a range of fields", async ({ page, api }) => {
		await three_field_format(api, PF_NAME);
		await open_builder(page, PF_NAME);

		const fields = page.locator("[data-pfb-section] .field");
		await expect(fields).toHaveCount(3);
		await fields.nth(0).click();
		await fields.nth(2).click({ modifiers: ["Shift"] });

		await expect(page.locator(".field--selected")).toHaveCount(3);
		await expect(page.locator(".pfb-inspector")).toContainText("Selection");
		await expect(page.locator(".pfb-inspector")).toContainText("3 fields");
	});

	test("cmd/ctrl-click toggles individual fields", async ({ page, api }) => {
		await three_field_format(api, PF_NAME);
		await open_builder(page, PF_NAME);

		const fields = page.locator("[data-pfb-section] .field");
		await fields.nth(0).click();
		await fields.nth(1).click({ modifiers: ["ControlOrMeta"] });
		await expect(page.locator(".field--selected")).toHaveCount(2);

		await fields.nth(0).click({ modifiers: ["ControlOrMeta"] });
		await expect(page.locator(".field--selected")).toHaveCount(1);
	});

	test("bulk Remove selected deletes the selected fields", async ({ page, api }) => {
		await three_field_format(api, PF_NAME);
		await open_builder(page, PF_NAME);

		const fields = page.locator("[data-pfb-section] .field");
		await fields.nth(0).click();
		await fields.nth(1).click({ modifiers: ["ControlOrMeta"] });
		await expect(page.locator(".field--selected")).toHaveCount(2);

		await page.locator(".es-button", { hasText: "Remove selected" }).first().click();

		await expect(page.locator("[data-pfb-section] .field:visible")).toHaveCount(1);
		await expect(page.locator(".field--selected")).toHaveCount(0);
	});

	test("padding handle drags to add section padding", async ({ page, api }) => {
		await three_field_format(api, PF_NAME);
		await open_builder(page, PF_NAME);
		await wait_for_canvas(page);

		await page.locator(".es-tabs__tab[data-tab='layers']").click();
		await tree_row(page, "Alpha").click();

		await drag(page, page.locator(".pfb-spacing-padding .pfb-space-grip-top"), 0, 40);

		await expect
			.poll(() =>
				css_number(
					page.locator(".pfb-section-active .print-format-section"),
					"padding-top"
				)
			)
			.toBeGreaterThan(10);
	});

	test("border-radius handle rounds the section corners", async ({ page, api }) => {
		await three_field_format(api, PF_NAME);
		await open_builder(page, PF_NAME);
		await wait_for_canvas(page);

		await page.locator(".es-tabs__tab[data-tab='layers']").click();
		await tree_row(page, "Alpha").click();

		await expect(page.locator(".pfb-radius-handle")).toBeAttached();
		await drag(page, page.locator(".pfb-radius-handle"), 30, 30);

		await expect
			.poll(() =>
				css_number(
					page.locator(".pfb-section-active .print-format-section"),
					"border-top-left-radius"
				)
			)
			.toBeGreaterThan(12);
	});
});

async function open_history(page) {
	await page
		.locator(".page-actions:visible")
		.locator('[title="Version History"], [data-original-title="Version History"]')
		.first()
		.click();
	await expect(page.locator(".pfb-history-list")).toBeVisible();
}

test.describe("Print Format Builder — draft and Save & Apply", () => {
	const page_status = (page) => page.locator('[data-testid="page-status"]:visible');
	const margin_top = (page) =>
		closest(
			page.locator(".pfb-margin-cell label", { hasText: "Top" }).first(),
			"pfb-margin-cell"
		).locator('input[type="number"]');

	test.beforeEach(async ({ page, api }) => {
		PF_NAME = track(`_Test PFB Draft ${Math.floor(Math.random() * 1e6)}`);
		await insert_builder_format(api, PF_NAME, []);
		await open_builder(page, PF_NAME);
		await expect(page.locator(".pfb-margin-grid")).toBeVisible();
		await expect(page.locator(".freeze")).toHaveCount(0);
	});

	test("autosaves into the draft without changing what prints", async ({ page, api }) => {
		await expect(page_status(page)).toHaveCount(0);

		const draft = wait_for_call(page, "save_draft");
		await set_input(margin_top(page), "17");

		expect((await draft).status()).toBe(200);
		await expect(page_status(page)).toContainText("Draft");

		const values = await get_format_values(api, PF_NAME, ["margin_top", "draft_data"]);
		expect(Number(values.margin_top)).not.toBe(17);
		expect(JSON.parse(values.draft_data).margin_top).toBe(17);
	});

	test("Save & Apply copies the draft onto the format and clears it", async ({ page, api }) => {
		await set_input(margin_top(page), "19");
		await expect(page_status(page)).toContainText("Draft");

		await save_and_apply(page);

		await expect(page_status(page)).toHaveCount(0);

		const values = await get_format_values(api, PF_NAME, ["margin_top", "draft_data"]);
		expect(Number(values.margin_top)).toBe(19);
		expect([null, ""]).toContain(values.draft_data);

		await open_history(page);
		await expect(page.locator(".pfb-history-list")).toContainText("Save & Apply");
	});

	test("keeps Typst block markup through Save & Apply", async ({ page, api }) => {
		const typst_pf_name = track(`${PF_NAME} Typst`);
		await api.insert_doc("Print Format", {
			name: typst_pf_name,
			doc_type: "ToDo",
			print_format_builder_beta: 1,
			pdf_generator: "Typst",
			format_data: JSON.stringify(
				builder_layout([
					{
						label: "",
						columns: [
							{
								label: "",
								fields: [
									{
										label: "Typst",
										fieldname: "typst_block_t",
										fieldtype: "Typst",
										custom: 1,
										typst: "Task: {{ doc.description }}",
									},
								],
							},
						],
					},
				])
			),
		});
		await open_builder(page, typst_pf_name);
		await expect(page.locator(".typst-block-source")).toContainText("doc.description");

		await set_input(margin_top(page), "18");
		await expect(page_status(page)).toContainText("Draft");
		await save_and_apply(page);

		const values = await get_format_values(api, typst_pf_name, ["format_data"]);
		expect(values.format_data).toContain("Task: {{ doc.description }}");
	});

	test("restoring the published version throws the draft away", async ({ page, api }) => {
		await set_input(margin_top(page), "23");
		await expect(page_status(page)).toContainText("Draft");

		await open_history(page);
		const discarded = wait_for_call(page, "discard_draft");
		const published = page
			.locator(".pfb-history-row", { hasText: "Published version" })
			.first();
		await published.hover();
		await published.locator(".pfb-history-action").first().click();
		await page.locator(".modal-footer .btn-modal-primary:visible").click();
		expect((await discarded).status()).toBe(200);

		await expect(page_status(page)).toHaveCount(0);

		const values = await get_format_values(api, PF_NAME, ["margin_top", "draft_data"]);
		expect(Number(values.margin_top)).not.toBe(23);
		expect([null, ""]).toContain(values.draft_data);
	});

	test("reopening the builder shows the draft, not what prints", async ({ page }) => {
		await set_input(margin_top(page), "29");
		await expect(page_status(page)).toContainText("Draft");

		await page.reload();
		await expect(page.locator(".pfb-margin-grid")).toBeVisible();

		await expect(page_status(page)).toContainText("Draft");
		await expect(margin_top(page)).toHaveValue("29");
	});
});
