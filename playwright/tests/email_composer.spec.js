import { test, expect } from "../support";

test.describe("Email Composer", () => {
	const test_user = "test_email_composer@example.com";

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc(
			"User",
			{
				email: test_user,
				first_name: "Test Email Composer",
				language: "de",
				send_welcome_email: 0,
			},
			true
		);
	});

	test("picks print language from the document, not the system language", async ({ page }) => {
		await page.goto(`/desk/user/${test_user}`);
		await expect.poll(() => page.evaluate(() => window.cur_frm?.doc?.language)).toBe("de");

		await page.evaluate(() => {
			new frappe.views.CommunicationComposer({ frm: cur_frm, doc: cur_frm.doc });
		});

		await expect(page.locator(".email-composer-modal .modal-dialog")).toBeVisible();
		await expect
			.poll(() => page.evaluate(() => window.cur_dialog?.get_value("print_language")))
			.toBe("de");
	});
});
