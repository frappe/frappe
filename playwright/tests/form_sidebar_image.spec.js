import { test, expect } from "../support";

const MENU_ITEMS = '.es-menu [role="menuitem"]';

test.describe("Form Sidebar Image", () => {
	test("opens the uploader directly when there is no photo", async ({ page, desk, api }) => {
		const doc = await api.insert_doc("Contact", { first_name: "Sidebar Image" });
		await page.goto(`/desk/contact/${doc.name}`);
		await desk.ready();
		await page.locator(".sidebar-image-wrapper:visible").click();
		await expect(page.locator(".es-menu[data-state='open']")).toHaveCount(0);
		await expect(desk.get_open_dialog()).toBeVisible();
	});

	test("offers upload and remove when there is a photo", async ({ page, desk, api }) => {
		const doc = await api.insert_doc("Contact", {
			first_name: "Sidebar Image",
			image: "/assets/frappe/images/default-avatar.png",
		});
		await page.goto(`/desk/contact/${doc.name}`);
		await desk.ready();
		await page.locator(".sidebar-image-wrapper:visible").click();
		await expect(page.locator(MENU_ITEMS)).toHaveCount(2);
		await expect(page.locator(MENU_ITEMS, { hasText: "Upload a photo" })).toBeVisible();
		await page.locator(MENU_ITEMS, { hasText: "Remove photo" }).click();
		await desk.click_modal_primary_button("Yes");
		await expect(page.locator(".sidebar-standard-image:visible")).toBeVisible();
	});
});
