import { test, expect } from "../support";

test.describe("Print View without System Manager", () => {
	const test_user = "test_print_view@example.com";
	const print_format = "Print View Format";

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_test_user", { username: test_user });
		await admin.call("frappe.tests.ui_test_helpers.add_remove_role", {
			action: "remove",
			user: test_user,
			role: "System Manager",
		});
		await admin.insert_doc("Print Format", { name: print_format, doc_type: "ToDo" }, true);
	});

	test("picking a format refreshes the preview", async ({ page, desk, api }) => {
		await desk.login(test_user);
		const todo = await api.insert_doc("ToDo", { description: "print view todo" });
		await page.goto(`/desk/print/ToDo/${todo.name}`);
		await desk.ready();

		await desk.fill_field("print_format", print_format, "Link");
		await expect(page.locator(".preview-beta-wrapper iframe")).toHaveAttribute(
			"src",
			/print_format=Print\+View\+Format/
		);
	});
});
