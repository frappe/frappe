import { test, expect } from "../support";

test.describe("User", () => {
	const email = "test_add_roles@example.com";

	test.afterEach(async ({ admin }) => {
		await admin.remove_doc("User", email, true);
	});

	test("Add Roles opens the roles of a user created outside the form", async ({
		page,
		desk,
	}) => {
		await page.goto("/desk/user");
		await desk.ready();
		await page.evaluate(
			(email) =>
				frappe.xcall("frappe.client.insert", {
					doc: {
						doctype: "User",
						email,
						first_name: "Test Add Roles",
						send_welcome_email: 0,
					},
				}),
			email
		);
		await page.locator(".msgprint-dialog").getByRole("button", { name: "Add Roles" }).click();

		await expect
			.poll(() =>
				page.evaluate(() => [frappe.get_route(), cur_frm?.get_active_tab()?.df.fieldname])
			)
			.toEqual([["Form", "User", email], "roles_permissions_tab"]);
	});
});
