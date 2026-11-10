import { test, expect } from "../support";

const group = (label, link_to) => [
	{ type: "Section Break", label, collapsible: 1, keep_closed: 1 },
	{ type: "Link", label: link_to, link_type: "DocType", link_to, child: 1 },
];

test.describe("Sidebar sections", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/todo");
		await desk.ready();
	});

	test("opens the group holding the page after switching from a shell with a group of the same name", async ({
		page,
	}) => {
		await page.evaluate(
			([first, second]) => {
				const sidebar = frappe.app.sidebar;
				frappe.boot.module_sidebars["Shell One"] = { name: "Shell One", items: first };
				frappe.boot.module_sidebars["Shell Two"] = { name: "Shell Two", items: second };

				sidebar.setup("Shell One");
				const todo = frappe.ui.sidebar_item.get_route(second[1], false, "Shell Two");
				history.replaceState(history.state, "", todo);
				sidebar.setup("Shell Two");
			},
			[group("Setup", "Note"), group("Setup", "ToDo")]
		);

		const active = page.locator(".body-sidebar .active-sidebar");
		await expect(active).toHaveText("ToDo");
		await expect(active).toBeVisible();
	});
});
