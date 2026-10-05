import { test, expect } from "../support";

// A saved Desktop Layout is laid over the icons the server sends, not used in their place.
//
// The layout is the user's order, folders and hidden flags. What an icon opens, and whether the
// user may see it at all, come from the server's icons, which carry the module each one opens and
// leave out what the user cannot reach. A layout saved before icons carried a module used to open
// nothing for any icon whose label is not a sidebar's name.
const BOOT = [
	{ name: "Invoicing", label: "Invoicing", icon_type: "Link", module: "Accounts" },
	{ name: "Ops Folder", label: "Operations", icon_type: "Folder" },
];

test.describe("Saved desktop layout", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/todo");
		await desk.ready();
		await page.evaluate(() => frappe.require("desktop_icons.bundle.js"));
	});

	const arrange = (page, layout) =>
		page.evaluate(
			([layout, boot]) => frappe.desktop_utils.arrange_layout(layout, boot),
			[layout, BOOT]
		);

	test("opens what the server says an icon opens", async ({ page }) => {
		const [icon] = await arrange(page, [
			{ name: "Invoicing", label: "Invoicing", icon_type: "Link" },
		]);
		expect(icon.module).toBe("Accounts");
		expect(icon.not_permitted).toBe(false);
	});

	test("finds an icon saved under a name it did not keep", async ({ page }) => {
		const [icon] = await arrange(page, [
			{ name: "new-desktop-icon-1", label: "Invoicing", icon_type: "Link" },
		]);
		expect(icon.module).toBe("Accounts");
	});

	test("does not draw an icon the server left out, and keeps it in the layout", async ({
		page,
	}) => {
		const [icon] = await arrange(page, [
			{ name: "Banking", label: "Banking", icon_type: "Link", idx: 3, hidden: 0 },
		]);
		expect(icon.not_permitted).toBe(true);
		// the user's own arrangement of it is untouched, for when it is allowed again
		expect(icon.idx).toBe(3);
	});

	test("always draws a folder", async ({ page }) => {
		const [folder] = await arrange(page, [
			{ name: "new-desktop-icon-2", label: "My Folder", icon_type: "Folder" },
		]);
		expect(folder.not_permitted).toBe(false);
	});
});
