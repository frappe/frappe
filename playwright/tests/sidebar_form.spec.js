import { test, expect } from "../support";

const desk_v2_fields = ["link_doctype", "link_to", "user", "navigation_items"];

function field(page, fieldname) {
	return page.locator(`.frappe-control[data-fieldname="${fieldname}"]`);
}

test.describe("Sidebar form", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	test.afterAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	test("hides the desk v2 fields on a new sidebar while desk v2 is off", async ({ page }) => {
		await page.goto("/desk/sidebar/new");
		await expect(field(page, "module")).toBeVisible();
		for (const fieldname of desk_v2_fields) {
			await expect(field(page, fieldname)).toBeHidden();
		}
	});

	test("hides the desk v2 fields on a saved v1 sidebar while desk v2 is off", async ({
		page,
	}) => {
		// a shipped v1 row: outside developer mode a new Sidebar cannot be saved
		await page.goto("/desk/sidebar/Users");
		await expect(field(page, "module")).toBeVisible();
		for (const fieldname of desk_v2_fields) {
			await expect(field(page, fieldname)).toBeHidden();
		}
	});

	test("shows the desk v2 fields while desk v2 is on", async ({ page, admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
		await page.goto("/desk/sidebar/new");
		for (const fieldname of desk_v2_fields) {
			await expect(field(page, fieldname)).toBeVisible();
		}
	});
});
