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
