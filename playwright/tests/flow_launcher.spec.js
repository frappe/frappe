import { test, expect } from "../support";

const SET_HIDDEN = "frappe.flow.launcher.set_hidden";

const launcher = (page) => page.locator("flow-launcher");
const icon = (page) => launcher(page).getByRole("button", { name: "Open Flow" });
const panel = (page) => launcher(page).locator(".panel");

// The chat in the panel, once /flow has loaded in it
async function chat(page) {
	const frame = await (await launcher(page).locator("iframe").elementHandle()).contentFrame();
	await expect.poll(() => frame.url()).toMatch(/^https?:\/\/[^/]+\/flow/);
	await frame.waitForLoadState();
	return frame;
}

async function hide_icon(page) {
	await icon(page).click({ button: "right" });
	const saved = page.waitForResponse((response) => response.url().includes(SET_HIDDEN));
	await launcher(page).getByRole("menuitem", { name: "Hide Flow icon" }).click();
	expect((await saved).ok()).toBe(true);
}

test.describe("Flow launcher", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/todo");
		await desk.ready();
	});

	test.afterEach(async ({ api }) => {
		await api.call(SET_HIDDEN, { hidden: false });
	});

	test("opens Flow in a panel that Ctrl+I minimizes and × closes", async ({ page }) => {
		await icon(page).click();
		await expect(panel(page)).not.toHaveAttribute("inert");
		await expect(icon(page)).toBeHidden();
		await (await chat(page)).evaluate(() => (window.marked = true));

		// from the chat, then from the page around it
		await page.keyboard.press("Control+i");
		await expect(panel(page)).toHaveAttribute("inert", "");
		await expect(icon(page)).toBeFocused();
		await page.keyboard.press("Control+i");
		await expect(panel(page)).not.toHaveAttribute("inert");
		expect(await (await chat(page)).evaluate(() => window.marked)).toBe(true);

		// closed, the next open starts a new chat
		await panel(page).getByRole("button", { name: "Close" }).click();
		await expect(panel(page)).toHaveAttribute("inert", "");
		await icon(page).click();
		await expect(launcher(page).locator("iframe")).toHaveAttribute("src", "/flow?new=1");
		expect(await (await chat(page)).evaluate(() => window.marked)).toBeUndefined();

		// Back from full screen goes back and shows the page
		await page.evaluate(() => frappe.set_route("List", "Note"));
		await expect(page).toHaveURL(/note/);
		await panel(page).getByRole("button", { name: "Full screen" }).click();
		await expect(panel(page)).toHaveAttribute("data-mode", "full");
		await page.goBack();
		await expect(page).toHaveURL(/todo/);
		await expect(panel(page)).not.toHaveAttribute("data-mode", "full");
	});

	test("keeps the icon hidden on every page until Undo", async ({ page, desk }) => {
		await hide_icon(page);
		await expect(icon(page)).toBeHidden();
		const saved = page.waitForResponse((response) => response.url().includes(SET_HIDDEN));
		await page.locator(".es-toast").getByRole("button", { name: "Undo" }).click();
		expect((await saved).ok()).toBe(true);
		await page.reload();
		await desk.ready();
		await expect(icon(page)).toBeVisible();

		await hide_icon(page);
		await page.reload();
		await desk.ready();
		await expect(launcher(page)).toHaveCount(0);
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
		const frame = await chat(page);
		const box = frame.locator("textarea");
		await expect(box).toHaveValue("plan my week");
		await expect.poll(() => frame.url()).toMatch(/\/flow\/?\?new=1$/);
		await expect(page.getByRole("dialog", { name: "Search and run" })).toHaveCount(0);
		await expect(box).toBeFocused();
		expect(await page.evaluate(() => document.activeElement.localName)).toBe("flow-launcher");
	});
});
