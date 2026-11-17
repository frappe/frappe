import { test, expect } from "../support";

test.describe("Announcement widget", () => {
	let original_settings;

	test.beforeAll(async ({ admin }) => {
		const settings = (await admin.get_doc("Navbar Settings", "Navbar Settings")).data;
		original_settings = {
			announcement_widget: settings.announcement_widget,
			dismissible_announcement_widget: settings.dismissible_announcement_widget,
		};
	});

	test.afterAll(async ({ admin }) => {
		await admin.set_value("Navbar Settings", "Navbar Settings", original_settings);
	});

	test("shows a changed announcement after the previous one was dismissed", async ({
		page,
		admin,
	}) => {
		await admin.set_value("Navbar Settings", "Navbar Settings", {
			announcement_widget: "<p>Desk maintenance on Saturday</p>",
			dismissible_announcement_widget: 1,
		});
		await page.goto("/desk");
		await page.locator(".announcement-widget .close-message").click();

		await admin.set_value("Navbar Settings", "Navbar Settings", {
			announcement_widget: "<p>Payroll closes on Friday</p>",
		});
		await page.reload();

		await expect(page.locator(".announcement-widget")).toContainText(
			"Payroll closes on Friday"
		);
	});
});
