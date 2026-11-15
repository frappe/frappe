import { test, expect } from "../support";
import { TEST_USER } from "../support/config";

const PROPERTY_SETTER = "ToDo-main-allow_split_view";

test.describe("Split View", () => {
	const stamp = `split-view-${Date.now()}`;
	const todos = [];

	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc(
			"Property Setter",
			{
				doc_type: "ToDo",
				doctype_or_field: "DocType",
				property: "allow_split_view",
				property_type: "Check",
				value: "1",
			},
			true
		);
		for (const label of ["one", "two", "three"]) {
			todos.push(
				await admin.insert_doc("ToDo", {
					description: `${stamp} ${label}`,
					allocated_to: TEST_USER,
				})
			);
		}
	});

	test.afterAll(async ({ admin }) => {
		for (const todo of todos) {
			await admin.remove_doc("ToDo", todo.name, true);
		}
		await admin.remove_doc("Property Setter", PROPERTY_SETTER, true);
	});

	const selected_row = (page) => page.locator(".split-view .es-item-list__row[data-selected]");
	const detail_title = (page) => page.locator(".split-view-preview-title");

	async function open_split_view(page) {
		const filter = encodeURIComponent(JSON.stringify(["like", `%${stamp}%`]));
		await page.goto(`/desk/todo/view/split?description=${filter}`);
		await expect(page.locator(".split-view .es-item-list__row")).toHaveCount(3);
		// the list's own order, newest first by default
		return page.evaluate(() => cur_list.data.map((doc) => doc.name));
	}

	test("opens the clicked record beside the list and puts it in the URL", async ({ page }) => {
		const names = await open_split_view(page);
		await expect(page.locator(".split-view-empty")).toContainText("Select a ToDo");

		await page.locator(".split-view .es-item-list__row").first().click();
		await expect(page).toHaveURL(new RegExp(`/view/split/${names[0]}\\?description=`));
		await expect(selected_row(page)).toHaveAttribute("data-id", names[0]);
		await expect(detail_title(page)).toContainText(stamp);
		await expect(
			page.locator(".split-view-preview-body .split-view-fields dt")
		).not.toHaveCount(0);
	});

	test("moves the selection with j and k, and Escape clears it", async ({ page }) => {
		const names = await open_split_view(page);
		await page.locator(".split-view .es-item-list__row").first().click();
		await expect(page).toHaveURL(new RegExp(`/view/split/${names[0]}`));
		// keys go to the page, not to the focused row
		await page.locator(".split-view-detail").click({ position: { x: 5, y: 5 } });

		await page.keyboard.press("j");
		await expect(page).toHaveURL(new RegExp(`/view/split/${names[1]}`));
		await expect(selected_row(page)).toHaveAttribute("data-id", names[1]);

		await page.keyboard.press("j");
		await expect(page).toHaveURL(new RegExp(`/view/split/${names[2]}`));

		await page.keyboard.press("k");
		await expect(page).toHaveURL(new RegExp(`/view/split/${names[1]}`));
		await expect(detail_title(page)).toContainText(stamp);

		await page.keyboard.press("Escape");
		await expect(page).toHaveURL(/\/view\/split\?description=/);
		await expect(selected_row(page)).toHaveCount(0);
		await expect(page.locator(".split-view-empty")).toContainText("3 records match");
	});

	test("shows a skeleton only for a slow load, and a record seen before at once", async ({
		page,
	}) => {
		const names = await open_split_view(page);
		const skeleton = page.locator(".split-view-preview-body .es-skeleton");
		const fields = page.locator(".split-view-preview-body .split-view-fields dt");
		let delay = 1500;
		await page.route("**/api/method/frappe.desk.doc_preview.get_preview*", async (route) => {
			await new Promise((resolve) => setTimeout(resolve, delay));
			await route.continue();
		});

		await page.locator(".split-view .es-item-list__row").first().click();
		// the header shows at once, the body stays empty until the skeleton's delay passes
		await expect(detail_title(page)).toContainText(stamp);
		await expect(skeleton).toHaveCount(0);
		await expect(skeleton).not.toHaveCount(0);
		await expect(fields).not.toHaveCount(0, { timeout: 5000 });

		await page.locator(".split-view .es-item-list__row").nth(2).click();
		await expect(fields).not.toHaveCount(0, { timeout: 5000 });
		// back to the first: drawn from memory, no skeleton and no wait for the slow server
		await page.locator(".split-view .es-item-list__row").first().click();
		await expect(page).toHaveURL(new RegExp(`/view/split/${names[0]}`));
		await expect(fields).not.toHaveCount(0, { timeout: 200 });
		await expect(skeleton).toHaveCount(0);
	});

	test("Back leaves the page instead of stepping through records", async ({ page }) => {
		await page.goto("/desk/todo");
		const names = await open_split_view(page);
		for (const name of names) {
			await page.locator(`.split-view .es-item-list__row[data-id="${name}"]`).click();
			await expect(page).toHaveURL(new RegExp(`/view/split/${name}`));
		}
		await page.goBack();
		await expect(page).not.toHaveURL(/\/view\/split/);
	});

	test("sends a DocType that did not opt in to its list", async ({ page }) => {
		await page.goto("/desk/note/view/split");
		await expect(page).toHaveURL(/\/note\/view\/list/);
		await expect(page.locator(".split-view")).toHaveCount(0);
	});
});
