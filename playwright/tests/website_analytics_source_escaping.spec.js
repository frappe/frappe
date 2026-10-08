import { test, expect } from "../support";

test.describe("Website Analytics", () => {
	const linked_source = "Web Page <b>newsletter</b>";
	const plain_source = "newsletter <b";
	const campaign = "spring sale <b";

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc(
			"Web Page View",
			{ path: "blog/introducing-frappe-framework-v16", source: linked_source },
			true
		);
		await admin.insert_doc(
			"Web Page View",
			{ path: "blog/scaling-frappe-in-production", source: plain_source },
			true
		);
		await admin.insert_doc(
			"Web Page View",
			{ path: "blog/whats-new-in-erpnext", campaign: campaign },
			true
		);
	});

	async function group_by(page, label) {
		await page.goto("/desk/query-report/Website Analytics");
		await expect(page.locator(".datatable")).toBeAttached({ timeout: 60000 });
		await page
			.locator('#page-query-report select[data-fieldname="group_by"]')
			.selectOption(label);
	}

	const cell = (page, text) => page.locator(".dt-cell__content", { hasText: text }).first();

	test("renders the source column as text", async ({ page }) => {
		await group_by(page, "Source");

		await expect(cell(page, linked_source)).toBeAttached();
		await expect(cell(page, plain_source)).toBeAttached();
		await expect(page.locator(".datatable .dt-cell__content b")).toHaveCount(0);
	});

	test("renders the campaign column as text", async ({ page }) => {
		await group_by(page, "Campaign");

		await expect(cell(page, campaign)).toBeAttached();
		await expect(page.locator(".datatable .dt-cell__content b")).toHaveCount(0);
	});
});
