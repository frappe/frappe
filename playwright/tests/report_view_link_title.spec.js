import { test, expect } from "../support";
import custom_link_title_doctype from "../fixtures/custom_link_title_doctype";

const doctype_name = custom_link_title_doctype.name;

async function expect_link_titles(page, selector, title) {
	await expect
		.poll(async () => [...new Set(await page.locator(selector).allTextContents())])
		.toEqual([title]);
}

test.describe("Report View Link Titles", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", custom_link_title_doctype, true);
		await admin.insert_doc(
			doctype_name,
			{
				title: "Renewal Reminder",
				display_name: "Renewal reminder for Contoso",
			},
			true
		);
		await admin.insert_doc(
			doctype_name,
			{
				title: "Contract Follow Up",
				display_name: "Contract follow up",
				parent_entry: "Renewal Reminder",
			},
			true
		);
		await admin.insert_doc(
			doctype_name,
			{
				title: "en",
				display_name: "English localization review",
			},
			true
		);
		await admin.insert_doc(
			doctype_name,
			{
				title: "Localization Handover",
				display_name: "Localization handover",
				parent_entry: "en",
				language: "en",
			},
			true
		);
	});

	test("takes titles from the report response, leaving a blank Link column empty", async ({
		page,
	}) => {
		const link_title_requests = [];
		page.on("request", (request) => {
			if (
				request.method() === "POST" &&
				request.url().includes("/api/method/frappe.desk.search.get_link_title")
			) {
				link_title_requests.push(request.url());
			}
		});

		await page.goto(`/desk/List/${doctype_name}/Report`);

		await expect_link_titles(
			page,
			`a[data-doctype="${doctype_name}"][data-name="Renewal Reminder"]`,
			"Renewal reminder for Contoso"
		);
		await expect(page.locator('a[data-name="null"]')).toHaveCount(0);
		expect(link_title_requests).toHaveLength(0);
	});

	test("resolves the title of each link against its own doctype", async ({ page }) => {
		await page.goto(`/desk/List/${doctype_name}/Report`);

		await expect_link_titles(page, `a[data-doctype="Language"][data-name="en"]`, "English");
		await expect_link_titles(
			page,
			`a[data-doctype="${doctype_name}"][data-name="en"]`,
			"English localization review"
		);
	});
});
