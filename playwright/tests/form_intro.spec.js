import { test, expect } from "../support";

test.describe("Form Intro", () => {
	test("keeps a single intro message after the first save of a new document", async ({
		page,
		desk,
	}) => {
		await desk.new_form("ToDo");

		await page.evaluate(() => {
			frappe.ui.form.on("ToDo", {
				refresh(frm) {
					frm.set_intro("Intro set from refresh", "blue");
				},
			});
			cur_frm.refresh();
		});

		const intro = page.locator(".page-container:visible .form-message");
		await expect(intro).toHaveCount(1);

		const description = await desk.fill_field(
			"description",
			"test intro dedupe",
			"Text Editor"
		);
		await description.blur();
		await expect
			.poll(() => page.evaluate(() => cur_frm.doc.description))
			.toContain("test intro dedupe");
		await desk.save();

		await expect(page.locator("body")).not.toHaveAttribute("data-route", /\/new-todo-/);
		await expect(page.locator("body")).toHaveAttribute("data-ajax-state", "complete");

		await expect(intro).toHaveCount(1);
	});
});
