import { test, expect } from "../support";

// Asks a question of a sidebar against a synthetic `module_sidebars` world, then puts the real
// one back. `question` is `[method, ...args]` on `frappe.ui.Sidebar.prototype`.
function ask(page, world, question) {
	return page.evaluate(
		([world, [method, ...args]]) => {
			const {
				sidebars,
				canonical = {},
				rail_hosts = {},
				url_shell = null,
				on_screen = null,
			} = world;
			const real = {
				module_sidebars: frappe.boot.module_sidebars,
				canonical_shell: frappe.boot.canonical_shell,
				app_rail_host: frappe.boot.app_rail_host,
				current_shell: frappe.router.current_shell,
			};

			frappe.boot.module_sidebars = Object.fromEntries(
				Object.entries(sidebars).map(([shell, value]) => {
					const { links = [], app } = Array.isArray(value) ? { links: value } : value;
					return [
						shell,
						{
							name: shell,
							module: shell,
							app,
							items: links.map((link_to) => ({ link_type: "DocType", link_to })),
						},
					];
				})
			);
			frappe.boot.canonical_shell = { DocType: canonical };
			frappe.boot.app_rail_host = rail_hosts;
			frappe.router.current_shell = url_shell;

			const sidebar = Object.create(frappe.ui.Sidebar.prototype);
			sidebar.current_module = on_screen;

			try {
				return sidebar[method](...args);
			} finally {
				frappe.boot.module_sidebars = real.module_sidebars;
				frappe.boot.canonical_shell = real.canonical_shell;
				frappe.boot.app_rail_host = real.app_rail_host;
				frappe.router.current_shell = real.current_shell;
			}
		},
		[world, question]
	);
}

const erpnext_hrms = {
	sidebars: {
		Accounts: { links: ["Journal Entry", "Sales Order"], app: "erpnext" },
		HR: { links: ["Job Applicant"], app: "hrms" },
	},
	canonical: {
		"Journal Entry": "Accounts",
		"Sales Order": "Accounts",
		"Job Applicant": "HR",
	},
};

const can_show_cases = [
	{
		case: "lets a shell show what it lists",
		world: {
			sidebars: { Stock: ["Item"], Selling: ["Customer"] },
			canonical: { Item: "Stock", Customer: "Selling" },
		},
		shell: "Selling",
		route: ["List", "Customer"],
		expected: true,
	},
	{
		case: "refuses a shell this user does not have",
		world: { sidebars: { Stock: ["Item"] }, canonical: { Item: "Stock" } },
		shell: "Not A Shell",
		route: ["List", "Item"],
		expected: false,
	},
	{
		case: "refuses a route that names no entity",
		world: { sidebars: { Stock: ["Item"] }, canonical: { Item: "Stock" } },
		shell: "Stock",
		route: [],
		expected: false,
	},
	{
		case: "keeps the shell for a route inside the same app",
		world: erpnext_hrms,
		shell: "Accounts",
		route: ["List", "Sales Order"],
		expected: true,
	},
	{
		case: "gives up the shell for a route that belongs to another app",
		world: erpnext_hrms,
		shell: "Accounts",
		route: ["List", "Job Applicant"],
		expected: false,
	},
	{
		case: "keeps a cross-app entity the shell curates a link to",
		world: {
			...erpnext_hrms,
			sidebars: {
				...erpnext_hrms.sidebars,
				Accounts: {
					links: ["Journal Entry", "Sales Order", "Job Applicant"],
					app: "erpnext",
				},
			},
		},
		shell: "Accounts",
		route: ["List", "Job Applicant"],
		expected: true,
	},
	{
		case: "keeps the shell when a companion app mounts on the same rail",
		world: {
			sidebars: {
				HR: { links: ["Job Applicant"], app: "hrms" },
				"India Payroll": { links: ["Salary Slip"], app: "india_payroll" },
			},
			canonical: { "Job Applicant": "HR", "Salary Slip": "India Payroll" },
			rail_hosts: { india_payroll: "hrms" },
		},
		shell: "HR",
		route: ["List", "Salary Slip"],
		expected: true,
	},
	{
		case: "keeps the shell when the entity belongs to no app",
		world: {
			sidebars: {
				Accounts: { links: ["Journal Entry"], app: "erpnext" },
				Widgets: { links: ["Widget"] },
			},
			canonical: { "Journal Entry": "Accounts", Widget: "Widgets" },
		},
		shell: "Accounts",
		route: ["List", "Widget"],
		expected: true,
	},
];

const shell_for_route_cases = [
	{
		case: "takes the shell the URL names",
		url_shell: "Selling",
		on_screen: "HR",
		expected: "Selling",
	},
	{
		case: "falls to the shell on screen when the URL names none",
		url_shell: null,
		on_screen: "Selling",
		expected: "Selling",
	},
	{
		case: "ignores a URL naming a shell that cannot show the route",
		url_shell: "HR",
		on_screen: null,
		expected: "Stock",
	},
	{
		case: "ignores a shell on screen that cannot show the route",
		url_shell: null,
		on_screen: "HR",
		expected: "Stock",
	},
	{
		case: "falls to where the entity opens when nothing holds",
		url_shell: null,
		on_screen: null,
		expected: "Stock",
	},
];

test.describe("Sidebar resolution", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/todo");
		await desk.ready();
	});

	test("decides whether a shell may show a route", async ({ page }) => {
		for (const { case: name, world, shell, route, expected } of can_show_cases) {
			await test.step(name, async () => {
				expect
					.soft(await ask(page, world, ["shell_can_show", shell, route]), name)
					.toBe(expected);
			});
		}
	});

	test("picks the shell a URL should name", async ({ page }) => {
		const world = {
			sidebars: {
				Stock: { links: ["Item"], app: "erpnext" },
				Selling: { links: ["Customer"], app: "erpnext" },
				HR: { links: ["Job Applicant"], app: "hrms" },
			},
			canonical: { Item: "Stock", Customer: "Selling", "Job Applicant": "HR" },
		};
		for (const { case: name, url_shell, on_screen, expected } of shell_for_route_cases) {
			await test.step(name, async () => {
				const shell = await ask(page, { ...world, url_shell, on_screen }, [
					"shell_for_route",
					["List", "Item"],
				]);
				expect.soft(shell, name).toBe(expected);
			});
		}
	});

	test("lands on the home shell the server worked out, else the first shell", async ({
		page,
	}) => {
		const result = await page.evaluate(() => {
			const sidebar = frappe.app.sidebar;
			const real = frappe.boot.home_shell;
			const shells = Object.keys(frappe.boot.module_sidebars);
			const other = shells.find((shell) => shell !== real && shell !== shells[0]);

			try {
				frappe.boot.home_shell = other;
				const with_home = sidebar.default_shell();
				frappe.boot.home_shell = null;
				return {
					other,
					with_home,
					without_home: sidebar.default_shell(),
					first: shells[0],
				};
			} finally {
				frappe.boot.home_shell = real;
			}
		});

		expect(typeof result.other, "no third shell here, so this test proves nothing").toBe(
			"string"
		);
		expect(result.with_home).toBe(result.other);
		expect(result.without_home).toBe(result.first);
	});
});
