import { test, expect } from "../support";

test.describe("Form Web Link", () => {
	const route = "test-web-link-page";

	test.beforeAll(async ({ admin, test_user_id }) => {
		await admin.remove_doc("Web Page", route, true);
		await admin.insert_doc("Web Page", {
			title: "Test Web Link Page",
			route: route,
			published: 1,
			content_type: "HTML",
			main_section_html: "<p>Test</p>",
		});
		await admin.set_value("User", test_user_id, { form_sidebar: 0 });
	});

	test.afterAll(async ({ admin, test_user_id }) => {
		await admin.set_value("User", test_user_id, { form_sidebar: 1 });
		await admin.remove_doc("Web Page", route, true);
	});

	test("renders a published website page when the form sidebar is disabled", async ({
		page,
	}) => {
		await page.goto(`/desk/web-page/${route}`);

		await expect(page.locator('.frappe-control[data-fieldname="title"]')).toBeVisible();
		await expect(page.locator('.frappe-control[data-fieldname="route"]')).toBeVisible();
	});
});
