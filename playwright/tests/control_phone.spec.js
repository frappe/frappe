import { test, expect } from "../support";
import doctype_with_phone from "../fixtures/doctype_with_phone";

test.describe("Control Phone", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", doctype_with_phone, true);
		await admin.remove_doc("Doctype With Phone", "Test Phone 1", true);
	});

	test("should set flag and data", async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();

		const dialog = await desk.dialog({
			title: "Phone",
			fields: [
				{
					fieldname: "phone",
					fieldtype: "Phone",
				},
			],
		});
		const selected_phone = page.locator(".selected-phone");
		const input = desk.get_field("phone");

		await selected_phone.click();
		await page.locator(".phone-picker .phone-wrapper[id='afghanistan']").click();
		await expect(selected_phone.locator(".country")).toHaveText("+93");
		await expect(selected_phone.locator("> img")).toHaveAttribute("src", /\/af\.svg/);

		await selected_phone.click();
		await page.locator(".phone-picker .phone-wrapper[id='india']").click();
		await expect(selected_phone.locator(".country")).toHaveText("+91");
		await expect(selected_phone.locator("> img")).toHaveAttribute("src", /\/in\.svg/);

		const phone_number = "9312672712";
		await selected_phone.locator("> img").click();
		await input.click();
		await page
			.locator(".frappe-control[data-fieldname=phone]")
			.getByRole("textbox")
			.first()
			.pressSequentially(phone_number);

		await expect(input).toHaveValue(phone_number);
		await input.blur();
		await expect
			.poll(() => dialog.evaluate((d) => d.get_value("phone")))
			.toBe("+91-" + phone_number);

		const search_text = "india";
		await selected_phone.click();
		const search = page.locator(".phone-picker .search-phones input");
		await search.click();
		await search.pressSequentially(search_text);
		const matching = await page
			.locator(`.phone-section .phone-wrapper[id*="${search_text.toLowerCase()}"]`)
			.count();
		expect(matching).toBeGreaterThan(0);
		await expect(page.locator(".phone-section .phone-wrapper:not(.hidden)")).toHaveCount(
			matching
		);
	});

	test("existing document should render phone field with data", async ({ page, desk, api }) => {
		await page.goto("/desk/doctype-with-phone");
		await desk.click_primary_button("Add Doctype With Phone");

		await desk.fill_field("title", "Test Phone 1");
		const phone = await desk.fill_field("phone", "+91-9823341234");
		await expect(phone).toHaveValue("9823341234");
		// the change fired on blur re-renders the Save button, which swallows a click in progress
		await phone.blur();
		await desk.save();
		const doc = await api.get_doc("Doctype With Phone", "Test Phone 1");
		expect(doc.data.phone).toBe("+91-9823341234");

		await desk.go_to_list("Doctype With Phone");
		const reloaded = page.waitForEvent("load");
		await desk.clear_cache();
		await reloaded;
		await desk.click_listview_row_item(0);
		await expect(page).toHaveTitle("Test Phone 1");
		await expect(page.locator(".selected-phone .country")).toHaveText("+91");
		await expect(page.locator(".selected-phone > img")).toHaveAttribute("src", /\/in\.svg/);
		await expect(desk.get_field("phone")).toHaveValue("9823341234");
	});
});
