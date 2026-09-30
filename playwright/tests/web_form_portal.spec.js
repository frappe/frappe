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

function visible_heading(page, text) {
	return page.locator(".web-form .section-head:visible", { hasText: text });
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
	const PAGES_ROUTE = "named-pages-note";

	test.use({ storageState: GUEST });

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", web_form_source_doctype, true);
	});

	test("Opens on the page that a Page Break in row 1 names", async ({ page, admin }) => {
		await seed_web_form(
			admin,
			[
				{ fieldtype: "Page Break", label: "About You" },
				{ fieldname: "title", fieldtype: "Data", label: "Title" },
				{ fieldtype: "Page Break", label: "More" },
				{ fieldname: "kind", fieldtype: "Select", label: "Kind" },
			],
			{
				title: PAGES_ROUTE,
				route: PAGES_ROUTE,
				doc_type: web_form_source_doctype.name,
				published: 1,
				login_required: 0,
			}
		);

		await page.goto(`/${PAGES_ROUTE}/new`);
		// the row names page 1, so the form does not open on a blank page
		await expect(
			page.locator('.web-form .frappe-control[data-fieldname="title"]')
		).toBeVisible();
		await expect(visible_heading(page, "About You")).toBeVisible();
		await expect(page.locator(".slides-progress .slide-step")).toHaveCount(2);

		await page.locator(".btn-next").click();
		await expect(
			page.locator('.web-form .frappe-control[data-fieldname="kind"]')
		).toBeVisible();
		await expect(visible_heading(page, "More")).toBeVisible();
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
