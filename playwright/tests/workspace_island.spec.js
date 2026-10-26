import { test, expect } from "../support";
import { TEST_USER } from "../support/config";

const WORKSPACE = "Playwright Island";
const CARD = "Playwright ToDo Count";
const CHART = "Playwright ToDo Chart";
const BLOCK = "Playwright Block";
const BLUE_BLOCK = "Playwright Blue Block";
const LATE_BLOCK = "Playwright Late Block";
const LAYOUT_ROLE = "Playwright Layout Role";
const LAYOUT_USER = "playwright-layout@example.com";
const SAVE_CHART_CONFIG = "dashboard_settings.save_chart_config";

test.describe("Workspace island", () => {
	test.beforeAll(async ({ admin }) => {
		const user = (await admin.get_doc("User", TEST_USER)).data;
		if (!user.roles.some((row) => row.role === "Workspace Manager")) {
			await admin.update_doc("User", TEST_USER, {
				roles: [...user.roles, { role: "Workspace Manager" }],
			});
		}
		await admin.insert_doc("Role", { role_name: LAYOUT_ROLE, desk_access: 1 }, true);
		await admin.insert_doc(
			"User",
			{
				email: LAYOUT_USER,
				first_name: "Layout",
				new_password: "Playwright-Layout-1",
				send_welcome_email: 0,
				roles: [{ role: LAYOUT_ROLE }],
			},
			true
		);
		await admin.insert_doc(
			"Number Card",
			{
				label: CARD,
				type: "Document Type",
				document_type: "ToDo",
				function: "Count",
				filters_json: "[]",
				is_public: 1,
			},
			true
		);
		await admin.insert_doc(
			"Dashboard Chart",
			{
				chart_name: CHART,
				chart_type: "Count",
				document_type: "ToDo",
				based_on: "creation",
				timeseries: 1,
				timespan: "Last Year",
				time_interval: "Monthly",
				type: "Bar",
				filters_json: "[]",
				is_public: 1,
			},
			true
		);
		await admin.insert_doc(
			"Custom HTML Block",
			{
				name: BLOCK,
				html: '<p class="pw-block">Static text</p>',
				style: "p { color: rgb(255, 0, 0); }",
				script: 'root_element.querySelector(".pw-block").textContent = "Written by script";',
			},
			true
		);
		await admin.insert_doc(
			"Custom HTML Block",
			{
				name: BLUE_BLOCK,
				html: '<p class="pw-blue">Blue text</p>',
				style: "p { color: rgb(0, 0, 255); }",
			},
			true
		);
		await admin.insert_doc(
			"Custom HTML Block",
			{
				name: LATE_BLOCK,
				html: '<div class="pw-late">Waiting</div>',
				script: `setTimeout(() => {
					root_element.querySelector(".pw-late").innerHTML = "<p>Filled</p>".repeat(10);
				}, 3000);`,
			},
			true
		);
		await admin.insert_doc(
			"Workspace",
			{
				label: WORKSPACE,
				title: WORKSPACE,
				module: "Desk",
				public: 1,
				renderer: "Frappe UI",
				content: JSON.stringify([
					{
						id: "pw-h1",
						type: "header",
						data: { text: '<span class="h4">First</span>' },
					},
					{ id: "pw-nc", type: "number_card", data: { number_card_name: CARD, col: 4 } },
					{ id: "pw-ch", type: "chart", data: { chart_name: CHART, col: 12 } },
					{
						id: "pw-sc",
						type: "shortcut",
						data: { shortcut_name: "Playwright ToDos", col: 4 },
					},
					{ id: "pw-cd", type: "card", data: { card_name: "Playwright Links", col: 4 } },
					{
						id: "pw-h2",
						type: "header",
						data: { text: '<span class="h4">Second</span>' },
					},
					{
						id: "pw-p",
						type: "paragraph",
						data: { text: "Playwright body text", col: 4 },
					},
					{
						id: "pw-cb",
						type: "custom_block",
						data: { custom_block_name: BLOCK, col: 4 },
					},
					{
						id: "pw-cb2",
						type: "custom_block",
						data: { custom_block_name: BLUE_BLOCK, col: 4 },
					},
					{
						id: "pw-cb3",
						type: "custom_block",
						data: { custom_block_name: LATE_BLOCK, col: 4 },
					},
					{
						id: "pw-ql",
						type: "quick_list",
						data: { quick_list_name: "Closed ToDos", col: 6 },
					},
				]),
				custom_blocks: [BLOCK, BLUE_BLOCK, LATE_BLOCK].map((name) => ({
					custom_block_name: name,
					label: name,
				})),
				quick_lists: [
					{
						document_type: "ToDo",
						label: "Closed ToDos",
						quick_list_filter: JSON.stringify([["ToDo", "status", "=", "Closed"]]),
					},
				],
				shortcuts: [{ type: "DocType", link_to: "ToDo", label: "Playwright ToDos" }],
				links: [
					{ type: "Card Break", label: "Playwright Links" },
					{ type: "Link", label: "Notes", link_type: "DocType", link_to: "Note" },
				],
				number_cards: [{ number_card_name: CARD, label: CARD }],
				charts: [{ chart_name: CHART, label: CHART }],
			},
			true
		);
	});

	let todo;
	test.beforeAll(async ({ admin }) => {
		todo = await admin.insert_doc("ToDo", {
			description: "Playwright open todo",
			status: "Open",
		});
	});

	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("ToDo", todo.name, true);
		await admin.remove_doc("Workspace", WORKSPACE, true);
	});

	test("draws a Frappe UI workspace at its usual URL", async ({ page }) => {
		const errors = [];
		page.on("pageerror", (error) => errors.push(error.message));

		await page.goto("/desk/playwright-island");

		const tile = page.locator(".ws-tile", { hasText: CARD });
		await expect(tile).toBeVisible();
		await expect(tile).toContainText(/\d/);
		await expect(page).toHaveTitle(new RegExp(WORKSPACE));
		await expect(page).toHaveURL(/\/desk\/playwright-island$/);
		expect(errors).toEqual([]);
	});

	test("a chart keeps its timespan across a reload, and Refresh redraws it", async ({
		page,
		api,
	}) => {
		await page.goto("/desk/playwright-island");
		const tile = page.locator(".ws-tile", { hasText: CHART });
		await expect(tile.getByRole("button", { name: "Chart actions" })).toBeVisible();
		await page.evaluate(() => frappe.dashboard_utils.get_dashboard_settings());
		await api.call(`frappe.desk.doctype.dashboard_settings.${SAVE_CHART_CONFIG}`, {
			reset: 1,
			config: {},
			chart_name: CHART,
		});
		await page.reload();

		const saved = page.waitForResponse((res) => res.url().includes(SAVE_CHART_CONFIG));
		await tile.getByRole("button", { name: "Last Year" }).click();
		await page.getByRole("menuitem", { name: "Last Quarter" }).click();
		await saved;

		await page.reload();
		await expect(tile.getByRole("button", { name: "Last Quarter" })).toBeVisible();

		const refreshed = page.waitForResponse((res) => res.url().includes("dashboard_chart.get"));
		await tile.getByRole("button", { name: "Chart actions" }).click();
		await page.getByRole("menuitem", { name: "Refresh" }).click();
		await refreshed;
	});

	test("a shortcut shows its count and a card link navigates", async ({ page }) => {
		await page.goto("/desk/playwright-island");

		const shortcut = page.locator(".ws-tile", { hasText: "Playwright ToDos" });
		await expect(shortcut.locator("text=/^\\d+$/")).toBeVisible();

		await page.locator(".ws-tile", { hasText: "Playwright Links" }).getByText("Notes").click();
		await expect(page).toHaveURL(/\/note(\?|$)/);
	});

	test("a heading stays above its own section on a phone", async ({ page }) => {
		await page.setViewportSize({ width: 400, height: 900 });
		await page.goto("/desk/playwright-island");

		const top = async (locator) => (await locator.boundingBox()).y;
		const second = page.locator(".ws-text", { hasText: "Second" });
		const body = page.locator(".ws-tile", { hasText: "Playwright body text" });
		const card = page.locator(".ws-tile", { hasText: "Playwright Links" });
		await expect(body).toBeVisible();

		expect(await top(card)).toBeLessThan(await top(second));
		expect(await top(second)).toBeLessThan(await top(body));
	});

	test("a quick list shows its filtered rows and the filter can change", async ({ page }) => {
		await page.goto("/desk/playwright-island");

		const list = page.locator(".ws-tile", { hasText: "Closed ToDos" });
		await expect(list.getByRole("button", { name: /^Filter/ })).toContainText("1");
		await expect(list.getByText("Playwright open todo")).toHaveCount(0);

		await list.getByRole("button", { name: "Clear All Filters" }).click();
		await expect(list.getByText("Playwright open todo").first()).toBeVisible();
	});

	test("a custom block runs its script in its own root", async ({ page }) => {
		await page.goto("/desk/playwright-island");

		const block = page.locator(".pw-block");
		await expect(block).toHaveText("Written by script");
		await expect(block).toHaveCSS("color", "rgb(255, 0, 0)");
		await expect(page.getByText("Playwright body text")).not.toHaveCSS(
			"color",
			"rgb(255, 0, 0)"
		);
	});

	test("custom blocks keep their styles apart, define no element and grow when filled", async ({
		page,
	}) => {
		await page.addInitScript(() => {
			window.__defined = [];
			const define = customElements.define.bind(customElements);
			customElements.define = (name, ...rest) => {
				window.__defined.push(name);
				return define(name, ...rest);
			};
		});
		await page.goto("/desk/playwright-island");

		await expect(page.locator(".pw-blue")).toHaveCSS("color", "rgb(0, 0, 255)");
		await expect(page.locator(".pw-block")).toHaveCSS("color", "rgb(255, 0, 0)");

		const late = page.locator(".ws-tile", { has: page.locator(".pw-late") });
		await expect(page.locator(".pw-late")).toHaveText("Waiting");
		const before = (await late.boundingBox()).height;
		await expect(page.locator(".pw-late p")).toHaveCount(10);
		await expect.poll(async () => (await late.boundingBox()).height).toBeGreaterThan(before);

		expect(await page.evaluate(() => window.__defined)).toEqual([]);
	});

	test("Manage finds a workspace by name and saves who can see it", async ({ page, api }) => {
		await page.goto("/desk/playwright-island");
		await expect(page.locator(".ws-tile", { hasText: CARD })).toBeVisible();
		await page.evaluate(() =>
			$(frappe.pages["workspace-view"].page.menu)
				.find(".dropdown-item")
				.filter((i, item) => item.innerText.trim() === "Manage")
				.click()
		);

		const dialog = page.getByRole("dialog");
		await dialog.getByPlaceholder("Search workspaces").fill("Playwright Isl");
		await expect(dialog.getByRole("tab")).toHaveCount(1);
		await dialog.getByRole("tabpanel").getByText("Playwright Island", { exact: true }).click();

		await dialog.getByLabel("Access").click();
		await page.getByRole("option", { name: "To a group of users" }).click();
		await dialog.getByRole("button", { name: "Add role" }).click();
		await dialog.getByRole("tabpanel").getByRole("combobox").last().click();
		await page.keyboard.type(LAYOUT_ROLE);
		await page.getByRole("option", { name: new RegExp(`^${LAYOUT_ROLE}`) }).click();
		await expect(dialog).toBeVisible();

		const saved = page.waitForResponse((res) =>
			res.url().includes("update_workspace_settings")
		);
		await dialog.getByRole("button", { name: "Save" }).click();
		expect((await saved).ok()).toBeTruthy();

		const settings = await api.call(
			"frappe.desk.doctype.workspace.workspace.get_workspace_settings",
			{
				name: WORKSPACE,
			}
		);
		expect(settings.message.roles).toEqual([LAYOUT_ROLE]);

		// the later cases read the workspace as a user without that role
		await api.call("frappe.desk.doctype.workspace.workspace.update_workspace_settings", {
			name: WORKSPACE,
			access: "public",
		});
	});

	test("the workspace page has no URL of its own", async ({ page }) => {
		await page.goto("/desk/workspace-view/playwright-island");
		await expect(
			page.getByText("This workspace does not exist, or you cannot open it.")
		).toBeVisible();
	});

	test("an editor moves a tile and the order holds after a reload", async ({ page }) => {
		const tile = (label) => page.locator(".ws-tile", { hasText: label });
		const tiles_in_order = async () =>
			(await page.locator(".ws-tile").allInnerTexts()).map((text) => text.split("\n")[0]);

		await page.goto("/desk/playwright-island");
		await expect(tile(CARD)).toBeVisible();
		await page.evaluate(() =>
			$(frappe.pages["workspace-view"].page.menu)
				.find(".dropdown-item")
				.filter((i, item) => item.innerText.trim() === "Edit")
				.click()
		);
		await expect(page).toHaveTitle(/Editing/);

		await tile("Playwright ToDos").locator(".ws-pick").dragTo(tile(CARD).locator(".ws-pick"));
		const saved = page.waitForResponse((res) => res.url().includes("save_page"));
		await page.getByRole("button", { name: "Save" }).click();
		expect((await saved).ok()).toBeTruthy();

		await page.reload();
		await expect(tile(CARD)).toBeVisible();
		const order = await tiles_in_order();
		expect(order.indexOf("Playwright ToDos")).toBeLessThan(order.indexOf(CARD));
	});

	test("an editor adds a Body text and a shortcut", async ({ page }) => {
		await page.goto("/desk/playwright-island");
		await expect(page.locator(".ws-tile", { hasText: CARD })).toBeVisible();
		await open_editor(page);

		await page.getByRole("button", { name: "Add text" }).click();
		await page.getByLabel("Text", { exact: true }).fill("Added by the editor");
		const panel = page.locator("aside");
		await panel.getByText("Body", { exact: true }).click();
		await panel.getByText("M", { exact: true }).click();

		await page.getByRole("button", { name: "Add block" }).click();
		await page.getByRole("menuitem", { name: "Shortcut" }).click();
		await page.getByLabel("Label").fill("Added Notes");
		await panel.getByRole("combobox").nth(1).click();
		await page.keyboard.type("Note");
		await page.getByRole("option", { name: /^Note\b(?! Seen)/ }).click();

		const saved = page.waitForResponse((res) => res.url().includes("save_page"));
		await page.getByRole("button", { name: "Save" }).click();
		expect((await saved).ok()).toBeTruthy();

		await page.reload();
		await expect(page.locator(".ws-tile", { hasText: "Added by the editor" })).toBeVisible();
		await expect(page.locator(".ws-tile", { hasText: "Added Notes" })).toBeVisible();
	});

	test("a role layout reaches only people holding the role", async ({ page, desk }) => {
		await page.goto("/desk/playwright-island");
		await expect(page.locator(".ws-tile", { hasText: CARD })).toBeVisible();
		await open_editor(page);

		await page.getByRole("button", { name: "Default" }).click();
		await page.getByRole("menuitem", { name: "New layout for a role" }).click();
		const role = page.locator(".modal.show input[data-fieldname='role']");
		await role.fill(LAYOUT_ROLE);
		await role.blur();
		await page.locator(".modal.show").getByRole("button", { name: "Create" }).click();

		await page.getByRole("button", { name: "Add text" }).click();
		await page.getByLabel("Text", { exact: true }).fill("Only for the role");
		const saved = page.waitForResponse((res) => res.url().includes("save_page"));
		await page.getByRole("button", { name: "Save" }).click();
		expect((await saved).ok()).toBeTruthy();

		await page.goto("/desk/playwright-island");
		await expect(page.locator(".ws-tile", { hasText: CARD })).toBeVisible();
		await expect(page.getByText("Only for the role")).toHaveCount(0);

		await desk.login(LAYOUT_USER, "Playwright-Layout-1");
		await page.goto("/desk/playwright-island");
		await expect(page.getByText("Only for the role")).toBeVisible();
	});

	test("an editor previews a role layout and deletes it", async ({ page }) => {
		await page.goto("/desk/playwright-island");
		await expect(page.locator(".ws-tile", { hasText: CARD })).toBeVisible();
		await open_editor(page);

		await page.getByRole("button", { name: "Default" }).click();
		await page.getByRole("menuitem", { name: `${LAYOUT_ROLE} · Site` }).click();
		await page.getByRole("button", { name: "Preview" }).click();
		await expect(page.getByText(`Previewing the ${LAYOUT_ROLE} layout`)).toBeVisible();
		await expect(page.getByText("Only for the role")).toBeVisible();

		await page.getByRole("button", { name: "More" }).click();
		await page.getByRole("menuitem", { name: "Delete layout" }).click();
		await page.locator(".modal.show").getByRole("button", { name: "Yes" }).click();
		await expect(page.getByRole("button", { name: "Default" })).toBeVisible();
		await expect(page.getByText("Only for the role")).toHaveCount(0);
	});

	test("the grid has 12, 6 and 2 columns at desk's breakpoints", async ({ page }) => {
		await page.goto("/desk/playwright-island");
		const grid = page.locator(".ws-grid").first();
		await expect(grid).toBeVisible();

		const columns = () =>
			grid.evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(" ").length);
		for (const [width, count] of [
			[1400, 12],
			[800, 6],
			[400, 2],
		]) {
			await page.setViewportSize({ width, height: 900 });
			await expect.poll(columns).toBe(count);
		}
	});

	test("an unknown workspace is not found", async ({ page }) => {
		await page.goto("/desk/no-such-playwright-workspace");
		await expect(page.getByText("Page no-such-playwright-workspace not found")).toBeVisible();
	});
});

test.describe("Switching renderer", () => {
	const SWITCH = "Playwright Switch";

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc(
			"Workspace",
			{
				label: SWITCH,
				title: SWITCH,
				module: "Desk",
				public: 1,
				renderer: "Legacy",
				content: JSON.stringify([
					{ id: "sw-h", type: "header", data: { text: "Switch me", col: 12 } },
				]),
			},
			true
		);
	});

	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("Workspace", SWITCH, true);
	});

	test("from either editor to the other", async ({ page }) => {
		await page.goto("/desk/playwright-switch");
		await page.waitForFunction(() => frappe.workspace?.editor);
		await expect(page.locator(".editor-js-container")).toBeVisible();
		await page.evaluate(() => frappe.workspace.start_editing());

		await page.getByRole("button", { name: "Switch to new layout" }).click();
		await page.locator(".modal.show").getByRole("button", { name: "Yes" }).click();
		await expect(page).toHaveTitle(/Editing/);
		await expect(page.getByRole("button", { name: "Save" })).toBeVisible();

		await page.getByRole("button", { name: "More" }).click();
		await page.getByRole("menuitem", { name: "Switch to old layout" }).click();
		await expect(page.getByRole("button", { name: "Switch to new layout" })).toBeVisible();
	});
});

async function open_editor(page) {
	await page.evaluate(() =>
		$(frappe.pages["workspace-view"].page.menu)
			.find(".dropdown-item")
			.filter((i, item) => item.innerText.trim() === "Edit")
			.click()
	);
	await expect(page).toHaveTitle(/Editing/);
}
