import { test, expect } from "../support";

test.describe("Print View without System Manager", () => {
	const test_user = "test_print_view@example.com";

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_test_user", { username: test_user });
		await admin.call("frappe.tests.ui_test_helpers.add_remove_role", {
			action: "remove",
			user: test_user,
			role: "System Manager",
		});
	});

	test("ctrl wheel zooms the preview", async ({ page, desk, api }) => {
		await desk.login(test_user);
		const todo = await api.insert_doc("ToDo", { description: "print view todo" });
		await page.goto(`/desk/print/ToDo/${todo.name}`);
		await desk.ready();

		const zoom_label = page.locator(".print-preview-bar .zoom-label");
		await expect(zoom_label).toHaveText("100%");
		await page.locator(".preview-beta-wrapper iframe").hover();
		await page.keyboard.down("Control");
		await page.mouse.wheel(0, -100);
		await expect(zoom_label).toHaveText("125%");
	});
});
