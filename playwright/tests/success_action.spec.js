import { test, expect } from "../support";

test.describe("Success Action", () => {
	let todo;

	test.afterEach(async ({ api }) => {
		if (todo) await api.remove_doc("ToDo", todo, true);
	});

	test("closes its toast once one of its actions is used", async ({ page }) => {
		await page.goto("/desk/todo");

		await page.evaluate(() => {
			frappe.boot.success_action = [
				{
					ref_doctype: "ToDo",
					first_success_message: "ToDo created",
					message: "ToDo created",
					next_actions: "email\nprint",
					action_timeout: 30,
				},
			];
			frappe.set_route("Form", "ToDo", "new");
		});
		await expect.poll(() => page.evaluate(() => window.cur_frm?.doctype)).toBe("ToDo");

		todo = await page.evaluate(async () => {
			cur_frm.set_value("description", "Success action toast");
			await cur_frm.save();
			return cur_frm.docname;
		});

		const toast = page.locator(".es-toast", { has: page.locator(".next-action-container") });
		await expect(toast).toBeVisible();

		await toast.locator(".next-action", { hasText: "Email" }).click();

		await expect(page.locator(".email-composer-modal .modal-dialog")).toBeVisible();
		await expect(toast).toHaveCount(0);
	});
});
