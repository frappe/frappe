import { test, expect } from "../support";

test.describe("Customize Form", () => {
	test("Changing to naming rule should update autoname", async ({ page, desk }) => {
		await page.goto("/desk/customize-form");
		await desk.ready();

		const doc_type = desk.get_field("doc_type", "Link");
		await doc_type.focus();
		await doc_type.pressSequentially("ToDo", { delay: 100 });
		await expect(
			page.locator('[data-fieldname="doc_type"] div[role="option"]').first()
		).toContainText("ToDo");
		await doc_type.press("Enter");
		await expect.poll(() => page.evaluate(() => cur_frm.doc.doc_type)).toBe("ToDo");
		await expect(page.getByRole("tab", { name: "Form", exact: true })).toHaveClass(/active/);
		await expect(page.locator(".form-builder-container")).toBeVisible();
		await page.getByRole("tab", { name: "Details", exact: true }).click();
		await desk.click_form_section("Naming");
		const naming_rule_default_autoname_map = {
			"Set by user": "prompt",
			"By fieldname": "field:",
			Expression: "",
			Random: "hash",
			"By script": "",
		};
		for (const [naming_rule, value] of Object.entries(naming_rule_default_autoname_map)) {
			await desk.fill_field("naming_rule", naming_rule, "Select");
			await expect(desk.get_field("autoname", "Data")).toHaveValue(value);
		}
	});
});
