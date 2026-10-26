import { test, expect } from "../support";

const WORKSPACE = "Playwright Island";
const CARD = "Playwright ToDo Count";

test.describe("Workspace island", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc(
			"Number Card",
			{
				label: CARD,
				type: "Document Type",
				document_type: "ToDo",
				function: "Count",
				filters_json: "[]",
				is_public: 1,
			},
			true
		);
		await admin.insert_doc(
			"Workspace",
			{
				label: WORKSPACE,
				title: WORKSPACE,
				module: "Desk",
				public: 1,
				renderer: "Frappe UI",
				content: JSON.stringify([
					{ id: "pw-nc", type: "number_card", data: { number_card_name: CARD, col: 4 } },
				]),
				number_cards: [{ number_card_name: CARD, label: CARD }],
			},
			true
		);
	});

	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("Workspace", WORKSPACE, true);
	});

	test("draws a Frappe UI workspace at its usual URL", async ({ page }) => {
		const errors = [];
		page.on("pageerror", (error) => errors.push(error.message));

		await page.goto("/desk/playwright-island");

		const tile = page.locator(".ws-tile", { hasText: CARD });
		await expect(tile).toBeVisible();
		await expect(tile).toContainText(/\d/);
		await expect(page).toHaveTitle(new RegExp(WORKSPACE));
		await expect(page).toHaveURL(/\/desk\/playwright-island$/);
		expect(errors).toEqual([]);
	});

	test("the workspace page has no URL of its own", async ({ page }) => {
		await page.goto("/desk/workspace-view/playwright-island");
		await expect(
			page.getByText("This workspace does not exist, or you cannot open it.")
		).toBeVisible();
	});
});
