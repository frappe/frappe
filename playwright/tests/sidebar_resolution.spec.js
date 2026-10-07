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

async function can_show(page, world, shell, route, expected) {
	expect(await ask(page, world, ["shell_can_show", shell, route])).toBe(expected);
}

test.describe("Sidebar resolution", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/todo");
		await desk.ready();
	});

	test.describe("a shell may show a route it lists", () => {
		const world = {
			sidebars: { Stock: ["Item"], Selling: ["Customer"] },
			canonical: { Item: "Stock", Customer: "Selling" },
		};

		test("lets a shell show what it lists", async ({ page }) => {
			await can_show(page, world, "Selling", ["List", "Customer"], true);
		});

		test("refuses a shell this user does not have", async ({ page }) => {
			await can_show(page, world, "Not A Shell", ["List", "Item"], false);
		});

		test("refuses a route that names no entity", async ({ page }) => {
			await can_show(page, world, "Stock", [], false);
		});
	});

	test.describe("the shell on screen holds inside its app, and only inside it", () => {
		const cross_app = {
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

		test("keeps the shell for a route inside the same app", async ({ page }) => {
			await can_show(page, cross_app, "Accounts", ["List", "Sales Order"], true);
		});

		test("gives up the shell for a route that belongs to another app", async ({ page }) => {
			await can_show(page, cross_app, "Accounts", ["List", "Job Applicant"], false);
		});

		test("keeps a cross-app entity the shell curates a link to", async ({ page }) => {
			const curated = {
				...cross_app,
				sidebars: {
					...cross_app.sidebars,
					Accounts: {
						links: ["Journal Entry", "Sales Order", "Job Applicant"],
						app: "erpnext",
					},
				},
			};

			await can_show(page, curated, "Accounts", ["List", "Job Applicant"], true);
		});

		test("keeps the shell when a companion app mounts on the same rail", async ({ page }) => {
			const companion = {
				sidebars: {
					HR: { links: ["Job Applicant"], app: "hrms" },
					"India Payroll": { links: ["Salary Slip"], app: "india_payroll" },
				},
				canonical: { "Job Applicant": "HR", "Salary Slip": "India Payroll" },
				rail_hosts: { india_payroll: "hrms" },
			};

			await can_show(page, companion, "HR", ["List", "Salary Slip"], true);
		});

		test("keeps the shell when the entity belongs to no app", async ({ page }) => {
			const unplaced = {
				sidebars: {
					Accounts: { links: ["Journal Entry"], app: "erpnext" },
					Widgets: { links: ["Widget"] },
				},
				canonical: { "Journal Entry": "Accounts", Widget: "Widgets" },
			};

			await can_show(page, unplaced, "Accounts", ["List", "Widget"], true);
		});
	});

	test.describe("which shell a URL should name", () => {
		const world = {
			sidebars: {
				Stock: { links: ["Item"], app: "erpnext" },
				Selling: { links: ["Customer"], app: "erpnext" },
				HR: { links: ["Job Applicant"], app: "hrms" },
			},
			canonical: { Item: "Stock", Customer: "Selling", "Job Applicant": "HR" },
		};
		const route = ["List", "Item"];
		const shell_for_route = (page, shells) =>
			ask(page, { ...world, ...shells }, ["shell_for_route", route]);

		test("takes the shell the URL names", async ({ page }) => {
			expect(await shell_for_route(page, { url_shell: "Selling", on_screen: "HR" })).toBe(
				"Selling"
			);
		});

		test("falls to the shell on screen when the URL names none", async ({ page }) => {
			expect(await shell_for_route(page, { url_shell: null, on_screen: "Selling" })).toBe(
				"Selling"
			);
		});

		test("ignores a URL naming a shell that cannot show the route", async ({ page }) => {
			expect(await shell_for_route(page, { url_shell: "HR", on_screen: null })).toBe(
				"Stock"
			);
		});

		test("ignores a shell on screen that cannot show the route", async ({ page }) => {
			expect(await shell_for_route(page, { url_shell: null, on_screen: "HR" })).toBe(
				"Stock"
			);
		});

		test("falls to where the entity opens when nothing holds", async ({ page }) => {
			expect(await shell_for_route(page, { url_shell: null, on_screen: null })).toBe(
				"Stock"
			);
		});
	});

	test.describe("the route that names nothing", () => {
		test("lands on the home shell the server worked out", async ({ page }) => {
			const result = await page.evaluate(() => {
				const sidebar = frappe.app.sidebar;
				const real = frappe.boot.home_shell;
				// Neither the home the server sent nor the first shell, which is the fallback: a
				// `default_shell` that ignored `home_shell` entirely would return either of those.
				const shells = Object.keys(frappe.boot.module_sidebars);
				const other = shells.find((shell) => shell !== real && shell !== shells[0]);
				if (!other) return { other };

				try {
					frappe.boot.home_shell = other;
					return { other, default_shell: sidebar.default_shell() };
				} finally {
					frappe.boot.home_shell = real;
				}
			});

			expect(typeof result.other, "no third shell here, so this test proves nothing").toBe(
				"string"
			);
			expect(result.default_shell).toBe(result.other);
		});

		test("falls to the first shell on a boot that carries no home", async ({ page }) => {
			const result = await page.evaluate(() => {
				const sidebar = frappe.app.sidebar;
				const real = frappe.boot.home_shell;

				try {
					frappe.boot.home_shell = null;
					return {
						default_shell: sidebar.default_shell(),
						first_shell: Object.keys(frappe.boot.module_sidebars)[0],
					};
				} finally {
					frappe.boot.home_shell = real;
				}
			});

			expect(result.default_shell).toBe(result.first_shell);
		});
	});
});
