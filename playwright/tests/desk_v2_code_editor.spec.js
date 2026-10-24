import { test, expect } from "../support";

test.describe("Desk v2 code editor", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
	});

	test.afterAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	test("starts five lines tall and grows to its cap", async ({ page }) => {
		await page.goto("/apps/desk/client-script/new");
		const field = page.locator('[data-fieldname="script"]');
		const editor = field.locator(".cm-editor");
		const content = field.locator(".cm-content");
		await expect(editor).toBeVisible();

		const lines_tall = await content.evaluate((el) => {
			const style = getComputedStyle(el);
			const inner =
				el.getBoundingClientRect().height -
				parseFloat(style.paddingTop) -
				parseFloat(style.paddingBottom);
			return inner / parseFloat(style.lineHeight);
		});
		expect(lines_tall).toBeCloseTo(5, 1);
		const empty_height = (await editor.boundingBox()).height;

		await content.click();
		for (let i = 1; i <= 7; i++) {
			await page.keyboard.type(`line ${i}`);
			await page.keyboard.press("Enter");
		}
		await expect(field.locator(".cm-line")).toHaveCount(8);
		expect((await editor.boundingBox()).height).toBeGreaterThan(empty_height);

		const expand = field.getByRole("button", { name: "Expand" });
		await expect(expand).toBeHidden();
		for (let i = 8; i <= 20; i++) {
			await page.keyboard.type(`line ${i}`);
			await page.keyboard.press("Enter");
		}
		await expect(expand).toBeVisible();
		const capped_height = (await editor.boundingBox()).height;
		await page.keyboard.type("line 21");
		await page.keyboard.press("Enter");
		expect((await editor.boundingBox()).height).toBe(capped_height);
	});
});
