import { test, expect } from "../support";

const launcher = (page) => page.locator("flow-launcher");
// Desk's Flow button, beside Search and Notifications in the dock or the sidebar
const toggle = (page) =>
	page.locator('.dock-utilities [aria-label="Flow"]:visible, .sidebar-flow:visible').first();
const panel = (page) => launcher(page).locator(".panel");

// The chat in the panel: the frappe.flow.chat island, once its header is up (a site with no
// model shows setup in place of the message box). Locators pierce its shadow root
async function chat(page) {
	const island = launcher(page).locator(".frappe-island");
	await expect(island.getByRole("button", { name: "Close", exact: true })).toBeVisible();
	return island;
}
// the island's own root, which keeps a mark for as long as the chat isn't mounted again
const mark = (island) =>
	island.locator(".frappe-island-root").evaluate((el) => (el.marked = true));
const marked = (island) => island.locator(".frappe-island-root").evaluate((el) => el.marked);

test.describe("Flow launcher", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/todo");
		await desk.ready();
	});

	test("opens Flow in a panel that Ctrl+I and × put away, its chat kept", async ({ page }) => {
		await toggle(page).click();
		await expect(panel(page)).not.toHaveAttribute("inert");
		await mark(await chat(page));

		// the page narrows beside it, and takes its room back once it's put away
		const margin = () =>
			page.evaluate(() => getComputedStyle(document.documentElement).marginRight);
		const width = await panel(page).evaluate((el) => el.getBoundingClientRect().width);
		await expect.poll(margin).toBe(`${width}px`);

		// from the chat, then from the page around it
		await page.keyboard.press("Control+i");
		await expect(panel(page)).toHaveAttribute("inert", "");
		await expect(launcher(page)).not.toBeFocused();
		await expect.poll(margin).toBe("0px");
		await page.keyboard.press("Control+i");
		await expect(panel(page)).not.toHaveAttribute("inert");
		expect(await marked(await chat(page))).toBe(true);

		// the header's × puts it away too, and the next open shows the same chat
		await (await chat(page)).getByRole("button", { name: "Close", exact: true }).click();
		await expect(panel(page)).toHaveAttribute("inert", "");
		await toggle(page).click();
		expect(await marked(await chat(page))).toBe(true);

		// a new tab takes the chat over from the panel
		const [tab] = await Promise.all([
			page.context().waitForEvent("page"),
			(await chat(page)).getByRole("button", { name: "Open in new tab" }).click(),
		]);
		await expect(tab).toHaveURL(/\/flow/);
		await expect(panel(page)).toHaveAttribute("inert", "");
	});

	test("keeps no sidebar or gear in the panel, however wide", async ({ page, desk }) => {
		// room beside the page for a panel past the chat's narrow layout
		await page.setViewportSize({ width: 1800, height: 960 });
		await page.addInitScript(() =>
			localStorage.setItem("flow_launcher", JSON.stringify({ width: 900 }))
		);
		await page.reload();
		await desk.ready();
		await toggle(page).click();
		const island = await chat(page);
		expect(await panel(page).evaluate((el) => el.getBoundingClientRect().width)).toBe(900);

		await expect(island.getByRole("button", { name: "Hide sidebar" })).toBeHidden();
		await expect(island.getByRole("button", { name: "Manage" })).toHaveCount(0);
	});

	test("opens and closes from an app's own element marked data-flow-toggle", async ({
		page,
	}) => {
		await page.evaluate(() => {
			const button = document.createElement("button");
			button.id = "app-flow-toggle";
			button.dataset.flowToggle = "";
			button.innerHTML = "<span>Flow</span>";
			document.body.prepend(button);
		});
		// a click inside it counts, wherever the app put it
		await page.locator("#app-flow-toggle span").dispatchEvent("click");
		await expect(panel(page)).not.toHaveAttribute("inert");
		await page.locator("#app-flow-toggle").dispatchEvent("click");
		await expect(panel(page)).toHaveAttribute("inert", "");
	});
});

test.describe("Flow from desk v2's palette", () => {
	const MODEL = "Flow Palette Model";

	// a model gives the built-in Assistant agent one, so a chat can start
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
		await admin.insert_doc(
			"Flow Model",
			{ title: MODEL, model_id: "openai/gpt-4o-mini" },
			true
		);
		await admin.update_doc("Flow Model", MODEL, { enabled: 1 });
	});

	// the Assistant keeps its model, so it is turned off rather than deleted
	test.afterAll(async ({ admin }) => {
		await admin.update_doc("Flow Model", MODEL, { enabled: 0 });
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	test("opens a new chat with the palette's text in its box, not sent", async ({ page }) => {
		await page.goto("/apps/desk");
		await expect(page.locator("html")).toHaveAttribute("data-flow", "ready");

		await page.getByRole("button", { name: "Search", exact: true }).click();
		await page.getByPlaceholder("Search or run an action").fill("plan my week");
		await page.getByRole("option", { name: /Ask Flow/ }).click();

		await expect(panel(page)).not.toHaveAttribute("inert");
		const island = await chat(page);
		const box = island.locator("textarea");
		await expect(box).toHaveValue("plan my week");
		// the text leaves the panel's route, which the next page opens
		const path = () => page.evaluate(() => JSON.parse(localStorage.flow_launcher).path);
		await expect.poll(path).toBe("/?new=1");
		await expect(page.getByRole("dialog", { name: "Search and run" })).toHaveCount(0);
		await expect(box).toBeFocused();
	});
});
