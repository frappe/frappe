import { test, expect, TEST_USER } from "../support";

const DOCK_OPEN = /(^|\s)dock-open(\s|$)/;

test.describe("Floating dock", () => {
	test.afterAll(async ({ admin }) => {
		await admin.set_value("User", TEST_USER, { language: "en", dock_mode: "Pinned" });
	});

	for (const { language, edge, far_edge } of [
		{ language: "en", edge: "left", far_edge: "right" },
		{ language: "ar", edge: "right", far_edge: "left" },
	]) {
		test(`opens from the ${edge} edge in ${language}`, async ({ page, desk, api }) => {
			await api.set_value("User", TEST_USER, { language, dock_mode: "Floating" });
			await page.goto("/desk/todo");
			await desk.ready();
			await expect(page.locator("body")).toHaveClass(/(^|\s)dock-active(\s|$)/);

			const width = await page.evaluate(() => document.documentElement.clientWidth);
			const x = { left: 0, right: width - 1, middle: Math.round(width / 2) };
			const y = 400;
			const body = page.locator("body");

			await page.mouse.move(x[far_edge], y);
			await expect(body).not.toHaveClass(DOCK_OPEN);

			await page.mouse.move(x[edge], y);
			await expect(body).toHaveClass(DOCK_OPEN);

			await page.mouse.move(x.middle, y);
			await expect(body).not.toHaveClass(DOCK_OPEN);
		});
	}
});
