import { test, expect } from "../support";
import web_form_source_doctype from "../fixtures/web_form_source_doctype";
import web_form_empty_source_doctype from "../fixtures/web_form_empty_source_doctype";
import {
	CANVAS,
	PAGE,
	ROUTE,
	SINGLE_PAGE_FIELDS,
	expect_web_form_fields,
	fill_new_web_form,
	open_get_fields,
	replace_web_form,
	seed_web_form,
	web_form_fields,
} from "../support/web_form";

const SOURCE_ROUTE = "source-note";
const SOURCE_DOCTYPE = "Web Form Source";
const EMPTY_ROUTE = "empty-source-note";

const OFFERED = [
	"title",
	"kind",
	"alpha_note",
	"bare_note",
	"bracket_note",
	"scripted_note",
	"flagged",
	"roles",
];

// every offered field, so the picker opens all-ticked, laid out the way an author would:
// a break the picker never adds, and two fields in an order the DocType does not have
const AUTHOR_LAYOUT = [
	{ fieldname: "kind", fieldtype: "Select", label: "Kind" },
	{ fieldname: "title", fieldtype: "Data", label: "Title" },
	{ fieldtype: "Section Break", label: "Author Section" },
	{ fieldname: "alpha_note", fieldtype: "Data", label: "Alpha Note" },
	{ fieldname: "bare_note", fieldtype: "Data", label: "Bare Note" },
	{ fieldname: "bracket_note", fieldtype: "Data", label: "Bracket Note" },
	{ fieldname: "scripted_note", fieldtype: "Data", label: "Scripted Note" },
	{ fieldname: "flagged", fieldtype: "Check", label: "Flagged" },
	{ fieldname: "roles", fieldtype: "Table MultiSelect", label: "Roles", options: "Has Role" },
];

// a Web Form is named after its scrubbed title, so passing the route as the title keeps
// the name and the route the same and the desk URL predictable
function seed_source_web_form(api, fields = [], doc_type = SOURCE_DOCTYPE, route = SOURCE_ROUTE) {
	return replace_web_form(api, {
		title: route,
		route: route,
		doc_type: doc_type,
		module: "Website",
		web_form_fields: fields,
	});
}

// the picker's own dialog, not whatever modal happens to be open
function picker(desk) {
	return desk.get_open_dialog().filter({ hasText: "Get Fields from" });
}

const checkbox = (desk, fieldname) =>
	picker(desk).locator(`input[type="checkbox"][data-unit='${fieldname}']`);

const label_area = (desk, fieldname) =>
	picker(desk).locator(`.label-area[data-unit='${fieldname}']`);

const warning_icon = (desk, fieldname) =>
	label_area(desk, fieldname).locator(".multicheck-warning-icon");

// bootstrap moves `title` aside once the tooltip is initialised
const tooltip = (desk, fieldname) => () =>
	warning_icon(desk, fieldname).getAttribute("data-original-title");

async function open_picker_on(desk, fields = []) {
	await seed_source_web_form(desk.api, fields);
	await open_get_fields(desk, SOURCE_ROUTE);
	await expect(picker(desk)).toBeVisible();
}

async function check_only(desk, fieldnames) {
	await picker(desk).locator('[data-action="unselect_all"]').click();
	for (const fieldname of fieldnames) {
		await checkbox(desk, fieldname).check();
	}
}

// a break carries a fieldname too, so the rows the author fills in are told apart by type
function is_input_row(row) {
	return !["Section Break", "Column Break", "Page Break"].includes(row.fieldtype);
}

function row_for(fields, fieldname) {
	return fields.find((d) => d.fieldname === fieldname);
}

// a dropped condition is simply absent, and the grid reads that back as null or ""
function expect_no_condition(fields, fieldname, key) {
	expect([null, ""], `${fieldname}.${key}`).toContain(row_for(fields, fieldname)[key] ?? null);
}

// a stale row cannot be seeded, because the server rejects a row naming a missing field.
// Point the form at ToDo in the UI instead, which shares no field with either source
async function open_picker_on_leftover_rows(desk, seed) {
	await seed(desk);
	// Get Fields flushes the builder first, so let it mount before the switch
	await expect(desk.page.locator(CANVAS)).toBeAttached();

	await desk.fill_field("doc_type", "ToDo", "Link");
	await desk.click_custom_action_button("Get Fields");
	await expect(picker(desk)).toBeVisible();
}

async function seed_source_and_open(desk, fields) {
	await seed_source_web_form(desk.api, fields);
	await desk.page.goto(`/desk/web-form/${SOURCE_ROUTE}`);
}

async function seed_note_and_open(desk) {
	await seed_web_form(desk.api, SINGLE_PAGE_FIELDS);
	await desk.page.goto(`/desk/web-form/${ROUTE}`);
}

test.describe("Web Form Get Fields", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", web_form_source_doctype, true);
		await admin.insert_doc("DocType", web_form_empty_source_doctype, true);
	});

	test("Offers every field a Web Form can render", async ({ desk }) => {
		await open_picker_on(desk);

		for (const fieldname of OFFERED) {
			await expect(checkbox(desk, fieldname)).toBeAttached();
		}

		await expect(checkbox(desk, "run_action")).toHaveCount(0);
		await expect(checkbox(desk, "secret_note")).toHaveCount(0);
	});

	test("Marks the mandatory fields and preselects them on an empty form", async ({ desk }) => {
		await open_picker_on(desk);

		await expect(label_area(desk, "title").locator(".text-danger")).toBeAttached();
		await expect(label_area(desk, "kind").locator(".text-danger")).toHaveCount(0);

		await expect(checkbox(desk, "title")).toBeChecked();
		await expect(checkbox(desk, "kind")).not.toBeChecked();
	});

	test("Names the condition a field carries", async ({ desk }) => {
		await open_picker_on(desk);

		await expect
			.poll(tooltip(desk, "alpha_note"))
			.toContain("Depends on: eval:doc.kind == 'Alpha'");

		await expect
			.poll(tooltip(desk, "flagged"))
			.toContain("eval:doc.kind == 'Beta', eval:doc.kind == 'Alpha'");

		await expect(warning_icon(desk, "kind")).toHaveCount(0);
	});

	test("Lists a repeated condition once", async ({ page, desk }) => {
		await seed_source_and_open(desk);
		await expect(page.locator(CANVAS)).toBeAttached();

		await page.evaluate((doctype) => {
			const df = frappe.meta.get_docfield(doctype, "flagged");
			df.read_only_depends_on = df.mandatory_depends_on;
		}, SOURCE_DOCTYPE);
		await desk.click_custom_action_button("Get Fields");

		await expect(warning_icon(desk, "flagged")).toHaveAttribute(
			"data-original-title",
			"Depends on: eval:doc.kind == 'Beta'"
		);
	});

	test("Filters the list as you type", async ({ desk }) => {
		await open_picker_on(desk);

		const unit = (fieldname) =>
			picker(desk).locator(`.unit-checkbox:has(.label-area[data-unit='${fieldname}'])`);
		const search = picker(desk).locator('[data-element="search"]');

		// the search is bound, cleared and focused only once the dialog has finished opening
		await expect(search).toBeFocused();
		await search.pressSequentially("alpha");

		await expect(unit("alpha_note")).toBeVisible();
		await expect(unit("title")).toBeHidden();
	});

	test("Ticks and unticks the whole list", async ({ desk }) => {
		await open_picker_on(desk);

		await picker(desk).locator('[data-action="unselect_all"]').click();
		await expect(picker(desk).locator('input[type="checkbox"]:checked')).toHaveCount(0);

		await picker(desk).locator('[data-action="select_all"]').click();
		await expect(picker(desk).locator('input[type="checkbox"]:not(:checked)')).toHaveCount(0);
	});

	test("Select Mandatory adds to the selection instead of replacing it", async ({ desk }) => {
		// a form with fields, so the picker does not tick the mandatory ones by itself
		await open_picker_on(desk, [{ fieldname: "kind", fieldtype: "Select", label: "Kind" }]);

		await expect(checkbox(desk, "title")).not.toBeChecked();

		await picker(desk).locator('[data-action="select_mandatory"]').click();

		await expect(checkbox(desk, "title")).toBeChecked();
		await expect(checkbox(desk, "kind")).toBeChecked();
	});

	test("Escapes a label that carries markup", async ({ desk }) => {
		await open_picker_on(desk, [
			{ fieldname: "kind", fieldtype: "Select", label: "<b>Kind</b>" },
		]);

		await expect(label_area(desk, "kind")).toContainText("<b>Kind</b>");
		await expect(label_area(desk, "kind").locator("b")).toHaveCount(0);
	});

	test("Falls back to the fieldname when nothing carries a label", async ({ desk }) => {
		await open_picker_on_leftover_rows(desk, () =>
			seed_source_and_open(desk, [{ fieldname: "kind", fieldtype: "Select" }])
		);

		await expect(label_area(desk, "kind")).toContainText("Kind");
	});

	test("Explains a row the picker can no longer add", async ({ desk }) => {
		await open_picker_on(desk, [
			{ fieldname: "secret_note", fieldtype: "Data", label: "Secret Note" },
			{ fieldname: "run_action", fieldtype: "Data", label: "Run Action" },
		]);

		await expect(label_area(desk, "secret_note")).toHaveClass(/(^|\s)text-muted(\s|$)/);
		await expect.poll(tooltip(desk, "secret_note")).toContain("Hidden in Web Form Source");

		await expect(label_area(desk, "run_action")).toHaveClass(/(^|\s)text-muted(\s|$)/);
		await expect.poll(tooltip(desk, "run_action")).toContain("cannot show this Button field");

		await expect(checkbox(desk, "secret_note")).toBeChecked();
	});

	test("Drops a condition when the fields it reads are left out", async ({ page, desk }) => {
		await open_picker_on(desk);

		await check_only(desk, [
			"alpha_note",
			"bare_note",
			"bracket_note",
			"scripted_note",
			"flagged",
		]);
		await desk.click_modal_primary_button("Update");

		await expect_web_form_fields(page, (fields) => {
			expect_no_condition(fields, "alpha_note", "depends_on");
			expect_no_condition(fields, "bare_note", "depends_on");
			expect_no_condition(fields, "bracket_note", "depends_on");
			expect_no_condition(fields, "flagged", "mandatory_depends_on");
			expect_no_condition(fields, "flagged", "read_only_depends_on");
		});
	});

	test("Carries a condition over when the field it reads is added too", async ({
		page,
		desk,
	}) => {
		await open_picker_on(desk);

		await picker(desk).locator('[data-action="select_all"]').click();
		await desk.click_modal_primary_button("Update");

		await expect_web_form_fields(page, (fields) => {
			expect(row_for(fields, "alpha_note").depends_on).toBe("eval:doc.kind == 'Alpha'");
			expect(row_for(fields, "bare_note").depends_on).toBe("kind");
			expect(row_for(fields, "bracket_note").depends_on).toBe("eval:doc['kind'] == 'Alpha'");
			expect(row_for(fields, "flagged").mandatory_depends_on).toBe(
				"eval:doc.kind == 'Beta'"
			);
			expect(row_for(fields, "flagged").read_only_depends_on).toBe(
				"eval:doc.kind == 'Alpha'"
			);
			expect_no_condition(fields, "scripted_note", "depends_on");
		});
	});

	test("Rebuilds the layout in doctype order", async ({ page, desk }) => {
		await open_picker_on(desk);

		await picker(desk).locator('[data-action="select_all"]').click();
		await desk.click_modal_primary_button("Update");

		await expect_web_form_fields(page, (fields) => {
			const placed = fields.filter(is_input_row).map((d) => d.fieldname);
			expect(placed).toEqual(OFFERED);
		});

		await expect(page.locator(CANVAS)).toBeVisible();
	});

	test("Leaves the layout alone when an Update adds nothing", async ({ page, desk }) => {
		await open_picker_on(desk, AUTHOR_LAYOUT);

		await expect(picker(desk).locator('input[type="checkbox"]:not(:checked)')).toHaveCount(0);
		await desk.click_modal_primary_button("Update");

		await expect_web_form_fields(page, (fields) => {
			// a break has no fieldname, so name it by type. Comparing the whole table checks the
			// order and the break's place at once. A rebuild would add the doctype's `more_tab` page
			const layout = (rows) => rows.map((d) => d.fieldname || d.fieldtype);
			expect(layout(fields), "the rows the author left").toEqual(layout(AUTHOR_LAYOUT));
		});
	});

	test("Names page 1 after the DocType's opening tab", async ({ page, desk }) => {
		await open_picker_on(desk);

		await picker(desk).locator('[data-action="select_all"]').click();
		await desk.click_modal_primary_button("Update");

		await expect_web_form_fields(page, (fields) => {
			// a Page Break in row 1 names page 1, so the opening tab opens no blank page
			expect(fields[0].fieldtype, "the opening tab is row 1").toBe("Page Break");
			expect(fields[0].label).toBe("Details");
			const pages = fields.filter((d) => d.fieldtype === "Page Break");
			expect(pages.map((d) => d.fieldname)).toEqual(["details_tab", "more_tab"]);
		});
	});

	test("Keeps the fields already on the form when it appends", async ({ page, desk }) => {
		await open_picker_on(desk, [
			{ fieldname: "kind", fieldtype: "Select", label: "Custom Kind Label" },
		]);

		// short of the whole list, or the update would rebuild the layout instead
		await check_only(desk, ["kind", "alpha_note"]);
		await desk.click_modal_primary_button("Update");

		await expect_web_form_fields(page, (fields) => {
			expect(row_for(fields, "kind").label).toBe("Custom Kind Label");
			expect(fields[0].fieldname).toBe("kind");
			expect(fields.map((d) => d.fieldname)).toContain("alpha_note");
		});
	});

	test("Removes the unticked rows and marks the form unsaved", async ({ page, desk }) => {
		await open_picker_on(desk, [
			{ fieldname: "kind", fieldtype: "Select", label: "Kind" },
			{ fieldname: "title", fieldtype: "Data", label: "Title" },
		]);

		await checkbox(desk, "kind").uncheck();
		await desk.click_modal_primary_button("Update");

		await expect_web_form_fields(page, (fields) => {
			expect(fields.map((d) => d.fieldname)).not.toContain("kind");
			expect(fields.map((d) => d.idx)).toEqual(fields.map((_, i) => i + 1));
		});
		await expect(page.locator(`${PAGE} [data-testid="page-status"]`)).toContainText(
			"Not Saved"
		);
	});

	test("Saves a web form left with no fields", async ({ page, desk }) => {
		await open_picker_on(desk, [{ fieldname: "kind", fieldtype: "Select", label: "Kind" }]);

		await picker(desk).locator('[data-action="unselect_all"]').click();
		await desk.click_modal_primary_button("Update");

		await expect.poll(() => web_form_fields(page)).toHaveLength(0);

		await desk.click_primary_button("Save");
		await expect(page.locator(`${PAGE} [data-testid="page-status"]`)).not.toContainText(
			"Not Saved"
		);
		await expect.poll(() => web_form_fields(page)).toHaveLength(0);
	});

	test("Says when a doctype has no fields to offer", async ({ page, desk, api }) => {
		await seed_source_web_form(api, [], "Web Form Empty Source", EMPTY_ROUTE);
		await page.goto(`/desk/web-form/${EMPTY_ROUTE}`);
		await expect(page.locator(CANVAS)).toBeAttached();

		await desk.click_custom_action_button("Get Fields");

		await expect(page.locator(".msgprint")).toContainText(
			"No fields are available from Web Form Empty Source"
		);
		await expect(desk.get_open_dialog()).not.toContainText("Get Fields from");
	});

	test("Get Fields survives the first save", async ({ page, desk }) => {
		await fill_new_web_form(desk, "Builder Note New");

		const collected = await web_form_fields(page);
		await desk.save();
		await expect.poll(() => web_form_fields(page)).toHaveLength(collected.length);
	});

	test("Marks the fields left over from the previous DocType", async ({ desk }) => {
		await open_picker_on_leftover_rows(desk, seed_note_and_open);

		await expect(checkbox(desk, "title")).toBeChecked();
		await expect(label_area(desk, "title")).toHaveClass(/(^|\s)text-muted(\s|$)/);
		await expect.poll(tooltip(desk, "title")).toContain("Not a field in ToDo");

		await expect(label_area(desk, "description")).not.toHaveClass(/(^|\s)text-muted(\s|$)/);
		await expect(warning_icon(desk, "description")).toHaveCount(0);
	});

	test("Removes a field left over from the previous DocType when it is unselected", async ({
		page,
		desk,
	}) => {
		await open_picker_on_leftover_rows(desk, seed_note_and_open);

		// nothing else is selected, so this is the add-and-remove path, not a rebuild
		await checkbox(desk, "title").uncheck();
		await desk.click_modal_primary_button("Update");

		await expect_web_form_fields(page, (fields) => {
			expect(fields.map((d) => d.fieldname)).not.toContain("title");
		});
	});

	test("Keeps a field left over from the previous DocType at the end of a rebuild", async ({
		page,
		desk,
	}) => {
		await open_picker_on_leftover_rows(desk, seed_note_and_open);

		await picker(desk).locator('[data-action="select_all"]').click();
		await desk.click_modal_primary_button("Update");

		await expect_web_form_fields(page, (fields) => {
			expect(fields.at(-1).fieldname, "the left over row is last").toBe("title");
		});
	});
});
