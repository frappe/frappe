import { test, expect } from "../support";

// The list view's filter on a v2 board: its quick filter boxes are rows in the panel, as on a list.

const BOARD = "_Test Filter Kanban";

const board_filters = (page) =>
	page.evaluate(() => cur_list._kanban.get_effective_filters().map((f) => f.slice(1, 4)));
const priority_box = (page) =>
	page.locator('.kanban-v2-quick-filters select[data-fieldname="priority"]');

test.describe("Kanban filter", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc(
			"Kanban Board",
			{
				kanban_board_name: BOARD,
				reference_doctype: "ToDo",
				field_name: "status",
				use_kanban_v2: 1,
				columns: [
					{ column_name: "Open", status: "Active", indicator: "Gray" },
					{ column_name: "Closed", status: "Active", indicator: "Gray" },
				],
				group_by_fields: [{ fieldname: "priority" }],
			},
			true
		);
	});

	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("Kanban Board", BOARD, true);
	});

	test("keeps a quick filter as a panel row, also while its field is the swimlane", async ({
		page,
		desk,
	}) => {
		await page.goto(`/desk/todo/view/kanban/${BOARD}`);
		await expect(page.locator(".kanban-v2-container")).toBeAttached();

		await priority_box(page).selectOption("Medium");
		await expect(page.locator(".filter-selector .filter-label")).toHaveText("1");
		await expect.poll(() => board_filters(page)).toEqual([["priority", "=", "Medium"]]);

		await desk.open_list_filter();
		await expect(page.locator(".filter-popover .filter-field select")).toHaveValue("Medium");
		await desk.close_list_filter();

		// the swimlane field has no box, so its filter stays in the panel
		await page.evaluate(() => cur_list._kanban.set_group_by("priority"));
		await expect(priority_box(page)).toHaveCount(0);
		await expect(page.locator(".filter-selector .filter-label")).toHaveText("1");
		expect(await board_filters(page)).toEqual([["priority", "=", "Medium"]]);

		// and goes back to the box once the board is not grouped by it
		await page.evaluate(() => cur_list._kanban.set_group_by(null));
		await expect(priority_box(page)).toHaveValue("Medium");
		expect(await board_filters(page)).toEqual([["priority", "=", "Medium"]]);
	});
});
