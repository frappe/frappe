import { test, expect } from "../support";

const SETTINGS = ["Disable Count", "Disable Comment Count", "Disable Sidebar Stats"];

async function save_list_settings(page, desk, { disabled }) {
	await desk.click_menu_button("List Settings");
	await expect(page.locator(".modal-dialog:visible")).toContainText(
		"DocType List View Settings"
	);
	for (const label of SETTINGS) {
		await page.getByLabel(label, { exact: true }).setChecked(disabled);
	}
	const saved = page.waitForResponse((res) =>
		res
			.url()
			.includes(
				"frappe.desk.doctype.list_view_settings.list_view_settings.save_listview_settings"
			)
	);
	await page.getByRole("button", { name: "Save", exact: true }).click();
	await saved;
}

test.describe("List View Settings", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/List/DocType/List");
		await desk.ready();
		await desk.clear_filters();
		await save_list_settings(page, desk, { disabled: false });
		await page.reload();
	});

	test("Default settings", async ({ page }) => {
		await expect(page.locator(".list-count")).toContainText("20 of");
	});

	test("disable count and sidebar stats then verify", async ({ page, desk }) => {
		await expect(page.locator(".list-count")).toContainText("20 of");
		await expect(page.locator(".frappe-list .comment-count svg.icon").first()).toBeVisible();
		await save_list_settings(page, desk, { disabled: true });

		await page.reload();
		await desk.ready();

		await expect(page.locator(".list-count")).toBeEmpty();
		await expect(page.locator(".list-sidebar .list-tags")).toHaveCount(0);
		await expect(page.locator(".frappe-list .comment-count")).toHaveCount(0);

		await save_list_settings(page, desk, { disabled: false });
	});
});
