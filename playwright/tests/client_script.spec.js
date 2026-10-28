import { test, expect } from "../support";

function collect_console_logs(page) {
	const logs = [];
	page.on("console", (message) => {
		if (message.type() === "log") {
			logs.push(message.text());
		}
	});
	return logs;
}

const script_names = [
	"Todo form script",
	"Todo list script",
	"Todo disabled list",
	"Todo form script 1",
	"Todo form script 2",
];

test.describe("Client Script", () => {
	test.afterAll(async ({ admin }) => {
		for (const name of script_names) {
			await admin.remove_doc("Client Script", name, true);
		}
	});

	test("should run form script in doctype form", async ({ page, api }) => {
		await api.insert_doc(
			"Client Script",
			{
				name: "Todo form script",
				dt: "ToDo",
				view: "Form",
				enabled: 1,
				script: `console.log('todo form script')`,
			},
			true
		);
		const logs = collect_console_logs(page);
		await page.goto("/desk/todo/new");
		await expect.poll(() => logs).toContain("todo form script");
	});

	test("should run list script in doctype list view", async ({ page, api }) => {
		await api.insert_doc(
			"Client Script",
			{
				name: "Todo list script",
				dt: "ToDo",
				view: "List",
				enabled: 1,
				script: `console.log('todo list script')`,
			},
			true
		);
		const logs = collect_console_logs(page);
		await page.goto("/desk/todo");
		await expect.poll(() => logs).toContain("todo list script");
	});

	test("should not run disabled scripts", async ({ page, desk, api }) => {
		await api.insert_doc(
			"Client Script",
			{
				name: "Todo disabled list",
				dt: "ToDo",
				view: "List",
				enabled: 0,
				script: `console.log('todo disabled script')`,
			},
			true
		);
		const logs = collect_console_logs(page);
		await page.goto("/desk/todo");
		await expect(page.locator("body")).toHaveAttribute("data-route", "List/ToDo/List");
		await desk.ready();
		expect(logs).not.toContain("todo disabled script");
	});

	test("should run multiple scripts", async ({ page, api }) => {
		await api.insert_doc(
			"Client Script",
			{
				name: "Todo form script 1",
				dt: "ToDo",
				view: "Form",
				enabled: 1,
				script: `console.log('todo form script 1')`,
			},
			true
		);
		await api.insert_doc(
			"Client Script",
			{
				name: "Todo form script 2",
				dt: "ToDo",
				view: "Form",
				enabled: 1,
				script: `console.log('todo form script 2')`,
			},
			true
		);
		const logs = collect_console_logs(page);
		await page.goto("/desk/todo/new");
		await expect.poll(() => logs).toContain("todo form script 1");
		await expect.poll(() => logs).toContain("todo form script 2");
	});
});

async function apply_to_options(page) {
	const select = page.locator('.frappe-control[data-fieldname="view"] select');
	return select.locator("option").evaluateAll((options) => options.map((o) => o.value));
}

test.describe("Client Script Apply To", () => {
	const record_script = "Todo record script";

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
	});

	test.afterAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 0 });
		await admin.remove_doc("Client Script", record_script, true);
	});

	test("offers only List and Form while desk v2 is off", async ({ page }) => {
		await page.goto("/desk/client-script/new");
		await expect.poll(() => apply_to_options(page)).toEqual(["List", "Form"]);
	});

	test("keeps Record on a Record script but hides Run Order while desk v2 is off", async ({
		page,
		api,
	}) => {
		await api.insert_doc(
			"Client Script",
			{
				name: record_script,
				dt: "ToDo",
				view: "Record",
				enabled: 0,
				script: "export default {};",
			},
			true
		);
		await page.goto(`/desk/client-script/${encodeURIComponent(record_script)}`);
		await expect(
			page.locator('.frappe-control[data-fieldname="view"] .control-value')
		).toHaveText("Record");
		await expect(page.locator('.frappe-control[data-fieldname="run_order"]')).toBeHidden();

		await page.evaluate(() => frappe.new_doc("Client Script", { dt: "ToDo", view: "Record" }));
		await expect.poll(() => apply_to_options(page)).toEqual(["List", "Form", "Record"]);
		await expect(page.locator('.frappe-control[data-fieldname="view"] select')).toHaveValue(
			"Record"
		);
	});

	test("keeps App Page but not Record on an App Page script while desk v2 is off", async ({
		page,
	}) => {
		await page.goto("/desk/client-script/new");
		await expect.poll(() => apply_to_options(page)).toEqual(["List", "Form"]);
		await page.evaluate(() =>
			frappe.new_doc("Client Script", { dt: "ToDo", view: "App Page" })
		);
		await expect.poll(() => apply_to_options(page)).toEqual(["List", "Form", "App Page"]);
		await expect(page.locator('.frappe-control[data-fieldname="view"] select')).toHaveValue(
			"App Page"
		);
	});

	test("offers Record and App Page while desk v2 is on", async ({ page, admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.set_desk_v2", { enabled: 1 });
		await page.goto("/desk/client-script/new");
		await expect
			.poll(() => apply_to_options(page))
			.toEqual(["List", "Form", "Record", "App Page"]);
	});
});
