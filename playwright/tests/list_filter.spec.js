import { test, expect } from "../support";

// The list view's filter: a panel of rows on desktop, a bottom sheet of rows on a phone.

const applied = (page) =>
	page.evaluate(() => cur_list.filter_area.get().map((f) => f.slice(1, 4)));
const box_value = (page, fieldname) =>
	page.evaluate((fieldname) => cur_list.page.fields_dict[fieldname].get_value(), fieldname);

test.describe("List filter", () => {
	test.describe("panel", () => {
		test("applies a filter as soon as it is complete", async ({ page, desk }) => {
			await desk.go_to_list("ToDo");
			await desk.clear_filters();

			await desk.open_list_filter();
			await desk.pick_filter_field("Status");
			await page.locator(".filter-popover .filter-field select").selectOption("Closed");

			await expect(page.locator(".filter-selector .filter-label")).toHaveText("1");
			await expect.poll(() => applied(page)).toContainEqual(["status", "=", "Closed"]);
			await expect(page.locator(".filter-popover .apply-filters")).toHaveCount(0);
			// Status has a box in the toolbar, so the filter shows there too
			await expect.poll(() => box_value(page, "status")).toBe("Closed");
		});

		test("keeps an edit to a toolbar filter's row when the panel closes", async ({
			page,
			desk,
		}) => {
			await desk.go_to_list("ToDo");
			await desk.clear_filters();
			await page.evaluate(() => cur_list.page.fields_dict.name.set_value("first"));

			await desk.open_list_filter();
			const value = page.locator(
				'.filter-popover .filter-field input[data-fieldname="name"]'
			);
			await expect(value).toHaveValue("first");
			await value.fill("second");
			const area = await page.locator(".layout-main-section").boundingBox();
			await page.mouse.click(area.x + area.width / 2, area.y + area.height - 5);

			await expect(page.locator(".filter-popover")).toHaveCount(0);
			await expect.poll(() => box_value(page, "name")).toBe("second");
		});

		test("a Check field filters only once Yes or No is chosen", async ({ page, desk }) => {
			await desk.go_to_list("Web Page");
			await desk.clear_filters();

			await desk.open_list_filter();
			await desk.pick_filter_field("Published");
			const select = page.locator(".filter-popover .filter-field select");
			await expect(select).toHaveValue("");
			expect(await applied(page)).toHaveLength(0);

			await select.selectOption("No");
			await expect.poll(() => applied(page)).toContainEqual(["published", "=", 0]);
		});
	});

	test.describe("Link in, with the combobox", () => {
		const panel = (page) => page.locator(".es-combobox__panel[data-state='open']");
		const search = (page) => panel(page).locator(".es-combobox__input");

		for (const condition of ["in", "not in"]) {
			test(`${condition}: search text that is no record is not a value`, async ({
				page,
				desk,
			}) => {
				await desk.go_to_list("ToDo");
				await desk.clear_filters();
				// the combobox for this page only: other tests run with the setting as it is
				await page.evaluate(() => (frappe.sys_defaults.enable_combobox_link_field = 1));
				await page.evaluate(
					(condition) =>
						cur_list.filter_area.add([
							["ToDo", "reference_type", condition, ["ToDo"]],
						]),
					condition
				);
				const kept = [["reference_type", condition, ["ToDo"]]];
				await expect.poll(() => applied(page)).toEqual(kept);
				await desk.open_list_filter();
				const value = page.locator(".filter-popover .filter-field .es-combobox__value");

				// Tab straight away, while the rows may still be loading
				await value.click();
				await search(page).pressSequentially("Not");
				await search(page).press("Tab");
				await expect(panel(page)).toHaveCount(0);
				expect(await applied(page)).toEqual(kept);

				// the "Use …" row is gone, and a click away drops the text too
				await value.click();
				await search(page).pressSequentially("Not");
				await expect(panel(page).getByText('Use "Not"')).toHaveCount(0);
				const area = await page.locator(".layout-main-section").boundingBox();
				await page.mouse.click(area.x + area.width / 2, area.y + area.height - 5);
				await expect(panel(page)).toHaveCount(0);
				expect(await applied(page)).toEqual(kept);

				// an exact name still picks its record (core DocTypes: no app is installed in CI)
				await expect(page.locator(".filter-popover")).toHaveCount(0);
				await desk.open_list_filter();
				await value.click();
				await search(page).pressSequentially("Note");
				// the rows have loaded the exact name, so Tab picks it
				await expect
					.poll(() =>
						page.evaluate(
							() =>
								!!cur_list.filter_area.filter_list.filters
									.find((f) => f.field)
									.field.combobox.match_option("Note")
						)
					)
					.toBe(true);
				await search(page).press("Tab");
				await expect
					.poll(() => applied(page))
					.toEqual([["reference_type", condition, ["ToDo", "Note"]]]);
			});
		}
	});

	test.describe("sheet on a phone", () => {
		test.use({ viewport: { width: 402, height: 800 } });

		const open_sheet = async (page) => {
			await page.locator(".filter-selector .filter-button").click();
			await expect(page.locator(".es-bottom-sheet")).toBeAttached();
		};
		const footer_button = (page, label) =>
			page.locator(".es-bottom-sheet__footer button", { hasText: label });
		const title = (page) => page.locator(".es-bottom-sheet__title");

		test.beforeEach(async ({ desk }) => {
			await desk.go_to_list("ToDo");
			await desk.clear_filters();
		});

		test("lists filters as rows and applies them on Apply", async ({ page }) => {
			await open_sheet(page);
			await expect(page.locator(".es-bottom-sheet")).toContainText("No filters applied");

			await footer_button(page, "Add filter").click();
			await expect(title(page)).toHaveText("New filter");
			await page.locator(".filter-sheet-edit .fieldname-select-area .es-combobox").click();
			await page.locator(".es-bottom-sheet__subheader input").fill("Status");
			await page
				.locator(".es-bottom-sheet__option:visible", { hasText: /^Status$/ })
				.click();
			await page.locator(".filter-sheet-edit .filter-field select").selectOption("Closed");
			await footer_button(page, "Done").click();

			const rows = page.locator(".filter-sheet-row");
			await expect(rows).toHaveCount(1);
			await expect(rows).toContainText("Status");
			await expect(rows).toContainText("Closed");
			expect(await applied(page)).toHaveLength(0);

			await footer_button(page, "Apply").click();
			await expect(page.locator(".es-bottom-sheet")).toHaveCount(0);
			await expect.poll(() => applied(page)).toContainEqual(["status", "=", "Closed"]);
		});

		test("picks a date and time in a calendar step, set on Done", async ({ page }) => {
			await page.evaluate(() =>
				cur_list.filter_area.add([["ToDo", "creation", ">", "2026-01-01 00:00:00"]])
			);

			await open_sheet(page);
			await page.locator(".filter-sheet-row__edit").click();
			const value = page.locator(".filter-sheet-edit .filter-field input");
			const before = await value.inputValue();
			await value.click();

			await expect(title(page)).toHaveText("Choose date and time");
			await expect(page.locator(".datepickers-container .datepicker.active")).toHaveCount(0);
			await page.locator(".filter-calendar .datepicker--button").click();
			await footer_button(page, "Done").click();

			await expect(title(page)).toHaveText("Edit filter");
			await expect(value).not.toHaveValue(before);
			await expect(value).not.toHaveValue("");
		});

		test("shows option labels, forgets an abandoned filter and discards edits without Apply", async ({
			page,
		}) => {
			await page.evaluate(() =>
				cur_list.filter_area.add([["ToDo", "creation", "Timespan", "last 7 days"]])
			);

			await open_sheet(page);
			const rows = page.locator(".filter-sheet-row");
			await expect(rows).toHaveCount(1);
			await expect(rows).toContainText("Last 7 Days");

			await footer_button(page, "Add filter").click();
			await page.locator(".es-bottom-sheet__back").click();
			await page.locator(".filter-sheet-row__edit").click();
			await expect(page.locator(".filter-sheet-edit .filter-box")).toHaveCount(1);
			await page.locator(".es-bottom-sheet__back").click();

			await page.locator(".filter-sheet-row .es-button").click();
			await expect(page.locator(".es-bottom-sheet")).toContainText("No filters applied");
			await page.locator(".es-bottom-sheet").dispatchEvent("keydown", { key: "Escape" });
			await expect(page.locator(".es-bottom-sheet")).toHaveCount(0);
			await expect
				.poll(() => applied(page))
				.toContainEqual(["creation", "Timespan", "last 7 days"]);
		});
	});
});
