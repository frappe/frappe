import { test, expect, GUEST } from "../support";
import web_form_source_doctype from "../fixtures/web_form_source_doctype";
import { seed_web_form } from "../support/web_form";

const ROUTE = "multiselect-note";

function seed_portal_form(api, roles_df = {}, more_fields = []) {
	return seed_web_form(
		api,
		[
			{ fieldname: "title", fieldtype: "Data", label: "Title", reqd: 1 },
			{
				fieldname: "roles",
				fieldtype: "Table MultiSelect",
				label: "Roles",
				options: "Has Role",
				...roles_df,
			},
			...more_fields,
		],
		{
			title: ROUTE,
			route: ROUTE,
			doc_type: web_form_source_doctype.name,
			published: 1,
			login_required: 0,
		}
	);
}

function roles_input(page) {
	return page.locator('.web-form .frappe-control[data-fieldname="roles"] input');
}

async function submit(page) {
	await page.locator(".web-form-actions button", { hasText: "Save" }).first().click();
}

test.describe("Web Form Table MultiSelect", () => {
	test.use({ storageState: GUEST });

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", web_form_source_doctype, true);
	});

	test("Guest picks an option shipped with the page and saves it", async ({
		page,
		desk,
		admin,
	}) => {
		await seed_portal_form(admin);

		// the desk search endpoint is not guest-allowed, so the control must not ask it
		const searches = [];
		page.on("request", (req) => {
			if (
				req.method() === "POST" &&
				req.url().includes("/api/method/frappe.desk.search.search_link")
			) {
				searches.push(req.url());
			}
		});

		await page.goto(`/${ROUTE}/new`);
		await desk.fill_field("title", "Multiselect Guest Note");
		await roles_input(page).pressSequentially("System Man");
		await page
			.locator('[role="option"]:visible', { hasText: "System Manager" })
			.first()
			.click();
		await expect(page.locator(".web-form .tb-selected-value .btn-link-to-form")).toHaveText(
			"System Manager"
		);

		// the list stays open after a pick and covers Save
		await roles_input(page).press("Escape");
		await submit(page);
		await expect(page.locator(".success-page")).toBeVisible();
		expect(searches).toHaveLength(0);

		const r = await admin.call("frappe.client.get_value", {
			doctype: web_form_source_doctype.name,
			filters: { title: "Multiselect Guest Note" },
			fieldname: "name",
		});
		const doc = await admin.call("frappe.client.get", {
			doctype: web_form_source_doctype.name,
			name: r.message.name,
		});
		expect(doc.message.roles.map((row) => row.role)).toEqual(["System Manager"]);
	});

	test("Next stops on a page that leaves a required Table MultiSelect empty", async ({
		page,
		desk,
		admin,
	}) => {
		await seed_portal_form(admin, { reqd: 1 }, [
			{ fieldtype: "Page Break", label: "More" },
			{ fieldname: "kind", fieldtype: "Select", label: "Kind" },
		]);

		await page.goto(`/${ROUTE}/new`);
		await desk.fill_field("title", "Multiselect Empty Note");
		await page.locator(".btn-next").click();

		const msgprint = page.locator(".msgprint");
		await expect(msgprint).toContainText("Mandatory fields required");
		await expect(msgprint).toContainText("Roles");
		await expect(page.locator(".btn-next")).toBeVisible();
	});
});

test.describe("Web Form Pages", () => {
	const PAGES_ROUTE = "paged-note";

	test.use({ storageState: GUEST });

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", web_form_source_doctype, true);
		await seed_web_form(
			admin,
			[
				{ fieldname: "title", fieldtype: "Data", label: "Title" },
				{ fieldtype: "Page Break", label: "More" },
				{ fieldname: "kind", fieldtype: "Select", label: "Kind" },
				{ fieldtype: "Section Break", label: "Extras" },
				{ fieldname: "alpha_note", fieldtype: "Data", label: "Alpha Note" },
				{ fieldtype: "Page Break" },
				{ fieldname: "bare_note", fieldtype: "Data", label: "Bare Note" },
			],
			{
				title: PAGES_ROUTE,
				route: PAGES_ROUTE,
				doc_type: web_form_source_doctype.name,
				published: 1,
				login_required: 0,
			}
		);
	});

	test("Shows the stepper above the fields and moves it with the page", async ({ page }) => {
		const stepper = page.locator(".web-form > .web-form-stepper:first-child");
		const label = stepper.locator(".es-progress__label");
		const hint = stepper.locator(".es-progress__hint");

		await page.goto(`/${PAGES_ROUTE}/new`);
		// a page with no Page Break label is named by its position
		await expect(label).toHaveText("Page 1");
		await expect(hint).toHaveText("Step 1 of 3");

		await page.locator(".btn-next").click();
		await expect(label).toHaveText("More");
		await expect(hint).toHaveText("Step 2 of 3");

		await page.locator(".btn-next").click();
		await expect(label).toHaveText("Page 3");

		await page.locator(".btn-previous").click();
		await expect(label).toHaveText("More");
		await expect(stepper.locator(".es-progress")).toHaveCount(1);
	});

	test("Names a page in the stepper only, not above its fields", async ({ page }) => {
		const headings = page.locator(".web-form .section-head:visible");

		await page.goto(`/${PAGES_ROUTE}/new`);
		await page.locator(".btn-next").click();
		await expect(page.locator(".web-form-stepper .es-progress__label")).toHaveText("More");
		// a Section Break on the page keeps its heading
		await expect(headings).toHaveText(["Extras"]);
	});
});

test.describe("Web Form Table", () => {
	const GRID_ROUTE = "grid-slideshow";

	test.use({ storageState: GUEST });

	test.beforeEach(async ({ admin }) => {
		// a child table with no Check column, since the portal grid posts a Check as "0"
		await seed_web_form(
			admin,
			[
				{ fieldname: "slideshow_name", fieldtype: "Data", label: "Name", reqd: 1 },
				{
					fieldname: "slideshow_items",
					fieldtype: "Table",
					label: "Slides",
					options: "Website Slideshow Item",
				},
			],
			{
				title: GRID_ROUTE,
				route: GRID_ROUTE,
				doc_type: "Website Slideshow",
				published: 1,
				login_required: 0,
			}
		);
	});

	test("Deletes a row from its row form and saves the rest", async ({ page, desk, admin }) => {
		const name = `Grid Delete ${Date.now()}`;
		await page.goto(`/${GRID_ROUTE}/new`);
		await desk.fill_field("slideshow_name", name);

		const table = page.locator('.web-form [data-fieldname="slideshow_items"]');
		for (const [i, heading] of ["One", "Two", "Three"].entries()) {
			const input = table.locator(
				`.grid-row[data-idx="${i + 1}"] [data-fieldname="heading"] input`
			);
			await table.locator(".grid-add-row").click();
			// Add row focuses the new row after a delay. Typing and moving on before it
			// lands loses what was typed
			await expect(input).toBeFocused();
			await input.click();
			await input.pressSequentially(heading);
		}

		await table.locator('.grid-row[data-idx="2"] .btn-open-row').click();
		await table.locator(".grid-row-open .grid-delete-row").click();

		await expect(table.locator(".grid-body .grid-row")).toHaveCount(2);

		await submit(page);
		await expect(page.locator(".success-page")).toBeVisible();

		const doc = await admin.call("frappe.client.get", { doctype: "Website Slideshow", name });
		expect(doc.message.slideshow_items.map((row) => row.heading)).toEqual(["One", "Three"]);
	});
});
