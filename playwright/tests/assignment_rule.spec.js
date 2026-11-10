import { test, expect } from "../support";

test.describe("Assignment Rule", () => {
	test("Custom grid buttons work", async ({ page, desk }) => {
		await desk.new_form("Assignment Rule");
		const all_days = page.getByRole("button", { name: "All Days", exact: true });
		await expect(all_days).toBeVisible();
		await all_days.click();
		await expect.poll(() => page.evaluate(() => cur_frm.doc.assignment_days.length)).toBe(7);
	});
});
