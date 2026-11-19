import { test, expect } from "../support";

test.describe("Navigation side in the settings dialog", () => {
	let sidebar, rail;

	test.beforeAll(async ({ admin }) => {
		await admin.set_value("User", "frappe@example.com", { navigation_side: "" });
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
		// A site sidebar and the rail row that opens it: the plain To Do page has no panel.
		sidebar = await admin.insert_doc("Sidebar", {
			title: "Side check",
			app: "frappe",
			key: "site:sidchk",
			user: "",
			navigation_items: [
				{
					key: "side-todo",
					item_type: "DocType",
					link_doctype: "DocType",
					link_to: "ToDo",
					added: 1,
				},
			],
		});
		rail = await admin.insert_doc("Rail", {
			app: "frappe",
			user: "",
			standard: 0,
			items: [
				{
					key: "site:sidrail",
					item_type: "DocType",
					link_doctype: "DocType",
					link_to: "ToDo",
					opens_sidebar: "site:sidchk",
					label: "Side check",
					added: 1,
				},
			],
		});
	});

	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("Rail", rail.name, true);
		await admin.remove_doc("Sidebar", sidebar.name, true);
		await admin.set_value("User", "frappe@example.com", { navigation_side: "" });
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	test("picking Right draws the rail on the right, and Site default brings them back", async ({
		page,
	}) => {
		await page.goto("/apps/desk/todo#settings/desk/profile");
		const dialog = page.getByRole("dialog");
		const side = dialog.locator('[data-fieldname="navigation_side"] button[role="combobox"]');
		const rail = page.locator("nav").first();
		const width = () => page.evaluate(() => document.documentElement.clientWidth);

		await expect(side).toContainText("Site default (Left)");
		expect((await rail.boundingBox()).x).toBeLessThan(60);

		await side.click();
		await page.getByRole("option", { name: "Right", exact: true }).click();

		await expect
			.poll(async () => (await rail.boundingBox()).x)
			.toBeGreaterThan((await width()) - 60);

		await side.click();
		await page.getByRole("option", { name: "Site default (Left)" }).click();
		await expect.poll(async () => (await rail.boundingBox()).x).toBeLessThan(60);
	});

	test("the seam and the toasts follow the side", async ({ page }) => {
		await page.goto("/apps/desk/todo?sidebar=site:sidchk");
		const seam = page.locator('button[aria-label="Collapse sidebar"]');
		// Outside the overlay the seam's parent is `display: contents` and has no box: the panel is its first sibling.
		const panel = seam.locator("xpath=preceding-sibling::*[last()]");
		await expect(seam).toBeVisible();
		await page.goto("/apps/desk/todo#settings/desk/profile");
		const side = page
			.getByRole("dialog")
			.locator('[data-fieldname="navigation_side"] button[role="combobox"]');
		await side.click();
		await page.getByRole("option", { name: "Right", exact: true }).click();
		await expect.poll(async () => (await panel.boundingBox()).x).toBeGreaterThan(400);
		await page.keyboard.press("Escape");

		// The seam sits on the panel's outer edge, which is its left one with the rail on the right.
		const edge = (await panel.boundingBox()).x;
		const box = await seam.boundingBox();
		expect(box.x + box.width / 2).toBeCloseTo(edge, 0);

		// A toast keeps clear of the rail: its right offset takes the navigation's inset.
		const gap = await page.evaluate(() => {
			const toaster = document.createElement("ol");
			toaster.setAttribute("data-sonner-toaster", "");
			toaster.setAttribute("data-x-position", "right");
			toaster.style.cssText = "position:fixed;--offset-right:16px";
			document.body.append(toaster);
			const inset = parseFloat(
				getComputedStyle(document.documentElement).getPropertyValue(
					"--shell-nav-inset-right"
				)
			);
			return { right: parseFloat(getComputedStyle(toaster).right), inset };
		});
		expect(gap.inset).toBeGreaterThan(40);
		expect(gap.right).toBeCloseTo(16 + gap.inset, 0);
	});
});
