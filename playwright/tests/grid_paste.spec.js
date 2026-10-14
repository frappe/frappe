import { test, expect } from "../support";

test.describe("Grid paste", () => {
	test("pasting several rows fills them and cancels the native paste", async ({
		page,
		desk,
	}) => {
		await desk.new_form("Contact");
		const table = page.locator('.frappe-control[data-fieldname="email_ids"]');
		await table.locator(".grid-add-row").click();
		const cell = table.locator('.grid-body [data-fieldname="email_id"]').first();
		await cell.click();
		const input = cell.locator("input");
		await expect(input).toBeFocused();

		const prevented = await input.evaluate((el) => {
			const clipboardData = new DataTransfer();
			clipboardData.setData("text/plain", "a@example.com\nb@example.com\n");
			const event = new ClipboardEvent("paste", {
				clipboardData,
				bubbles: true,
				cancelable: true,
			});
			el.dispatchEvent(event);
			return event.defaultPrevented;
		});

		expect(prevented).toBe(true);
		await expect
			.poll(() => page.evaluate(() => cur_frm.doc.email_ids.map((row) => row.email_id)))
			.toEqual(["a@example.com", "b@example.com"]);
	});
});
