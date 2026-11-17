import { test, expect } from "../support";

test.describe("Number Card", () => {
	test("Check filter populate for child table doctype", async ({ page, desk }) => {
		await desk.new_form("Number Card");
		await expect(
			page.locator('.frappe-control[data-fieldname="parent_document_type"]')
		).toHaveCSS("display", "none");

		await desk.fill_field("document_type", "Workspace Link", "Link");
		await expect(desk.get_field("document_type", "Link")).toHaveValue("Workspace Link");

		await desk.fill_field("label", "Test Number Card", "Data");
		await expect(desk.get_field("parent_document_type", "Link")).toHaveValue("Workspace");

		await page.locator('[data-fieldname="filters_json"]').click();
		await page.locator(".modal-body .filter-action-buttons .add-filter").click();
		await page.locator(".modal-body .fieldname-select-area").click();
		await page.locator(".modal-actions .btn-modal-close").click();
	});
});

const DASHBOARD = "TEST-NUMBER-CARD-WIDGET";
const COUNT_CARD = "Test Number Card Count";
const AMOUNT_CARD = "Test Number Card Amount";
const DURATION_CARD = "Test Number Card Duration";
const DURATION_DOCTYPE = "Test Number Card Duration";
const REPORT = "Test Number Card Report";
const MARKER = "number card widget test";

const set_classic_charts = (admin, value) =>
	admin.set_value("System Settings", "System Settings", { use_classic_charts: value });

const days_ago = (days) =>
	new Date(Date.now() - days * 86400000).toISOString().slice(0, 19).replace("T", " ");

async function open_card(page, label) {
	await page.goto(`/desk/dashboard-view/${DASHBOARD}`);
	return page.locator(".number-widget-box").filter({ hasText: label });
}

test.describe("Number Card widget", () => {
	let original;

	test.beforeAll(async ({ admin }) => {
		original = (await admin.get_doc("System Settings", "System Settings")).data
			.use_classic_charts;

		const filters = [["ToDo", "description", "like", `%${MARKER}%`]];
		for (const todo of (await admin.get_list("ToDo", ["name"], filters)).data) {
			await admin.remove_doc("ToDo", todo.name);
		}
		// two of four existed a month ago, so the count grew by 100 %
		for (let i = 0; i < 4; i++) {
			const todo = await admin.insert_doc("ToDo", { description: MARKER });
			if (i < 2) {
				await admin.call("frappe.tests.ui_test_helpers.db_set_values", {
					doctype: "ToDo",
					name: todo.name,
					values: { creation: days_ago(60) },
				});
			}
		}

		await admin.insert_doc(
			"Report",
			{
				report_name: REPORT,
				ref_doctype: "ToDo",
				report_type: "Query Report",
				is_standard: "No",
				query: 'select 123456.5 as "Amount:Currency:120"',
			},
			true
		);

		await admin.remove_doc("Dashboard", DASHBOARD, true);
		for (const card of [COUNT_CARD, AMOUNT_CARD, DURATION_CARD]) {
			await admin.remove_doc("Number Card", card, true);
		}

		await admin.insert_doc("Number Card", {
			label: COUNT_CARD,
			type: "Document Type",
			document_type: "ToDo",
			function: "Count",
			filters_json: JSON.stringify(filters),
			show_percentage_stats: 1,
			stats_time_interval: "Monthly",
		});

		await admin.insert_doc("Number Card", {
			label: AMOUNT_CARD,
			type: "Report",
			report_name: REPORT,
			report_field: "amount",
			report_function: "Sum",
			function: "Sum",
		});

		await admin.call("frappe.tests.ui_test_helpers.create_doctype", {
			name: DURATION_DOCTYPE,
			fields: [{ label: "Time", fieldname: "time", fieldtype: "Duration", hide_seconds: 1 }],
		});
		for (const doc of (await admin.get_list(DURATION_DOCTYPE, ["name"])).data) {
			await admin.remove_doc(DURATION_DOCTYPE, doc.name);
		}
		await admin.insert_doc(DURATION_DOCTYPE, { time: 3725 });

		await admin.insert_doc("Number Card", {
			label: DURATION_CARD,
			type: "Document Type",
			document_type: DURATION_DOCTYPE,
			function: "Sum",
			aggregate_function_based_on: "time",
			filters_json: "[]",
			// left out, it takes the default currency, which the classic card prints
			currency: "",
		});

		await admin.insert_doc("Dashboard", {
			name: DASHBOARD,
			dashboard_name: DASHBOARD,
			is_standard: 0,
			cards: [{ card: COUNT_CARD }, { card: AMOUNT_CARD }, { card: DURATION_CARD }],
		});
	});

	test.afterAll(async ({ admin }) => {
		await set_classic_charts(admin, original || 0);
	});

	test("draws frappe-ui's NumberCard, printing the number as the classic card does", async ({
		page,
		admin,
	}) => {
		await set_classic_charts(admin, 1);
		const classic = await open_card(page, AMOUNT_CARD);
		await expect(classic.locator(".widget-content .number")).toBeVisible();
		await expect(classic.locator(".frappe-island")).toHaveCount(0);
		const amount = (await classic.locator(".widget-content .number").innerText()).trim();
		expect(amount).toMatch(/\d/);

		await set_classic_charts(admin, 0);
		const card = await open_card(page, AMOUNT_CARD);
		const island = card.locator(".frappe-island");
		await expect(island.getByText(amount, { exact: true })).toBeVisible();
		await expect(card.locator(".widget-content .number")).toHaveCount(0);
		await expect(card.locator(".widget-title")).toHaveText(AMOUNT_CARD);
	});

	test("a Duration card reads as its field prints it, seconds hidden, in both modes", async ({
		page,
		admin,
	}) => {
		await set_classic_charts(admin, 1);
		const classic = await open_card(page, DURATION_CARD);
		await expect(classic.locator(".widget-content .number")).toHaveText("1h 2m");

		await set_classic_charts(admin, 0);
		const island = (await open_card(page, DURATION_CARD)).locator(".frappe-island");
		await expect(island.getByText("1h 2m", { exact: true })).toBeVisible();
	});

	test("a Document Type card shows its count and its change since last month", async ({
		page,
		admin,
	}) => {
		await set_classic_charts(admin, 0);
		const island = (await open_card(page, COUNT_CARD)).locator(".frappe-island");

		await expect(island.getByText("4", { exact: true })).toBeVisible();
		await expect(island.getByText("100%", { exact: true })).toBeVisible();
		await expect(island.getByText("since last month", { exact: true })).toBeVisible();
	});
});
