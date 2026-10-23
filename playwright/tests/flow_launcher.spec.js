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
