// Which sidebar a route shows, on the client.
//
// Most of what used to be tested here is gone, not because it stopped mattering but because it
// moved: `bootinfo.canonical_shell` says where each entity opens, worked out once per user on the
// server, and `frappe/desk/doctype/sidebar/test_sidebar.py` is where that order is tested now. A
// six-step ladder that re-resolved itself once a doctype's meta arrived used to live in the desk;
// what is left is two questions.
//
// `shell_can_show` asks whether a named shell may show a route. `shell_for_route` asks which shell
// to name, and answers with the first of three that can: the URL's, the one on screen, or where
// the entity opens on its own.
//
// Every case is synthetic. Nothing here depends on which app is installed, and the payloads
// reproduce shapes measured on a site with erpnext and hrms.
context("Sidebar resolution", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/todo");
	});

	// A `module_sidebars` payload from a compact spelling. Only what the two questions read is
	// filled in: what a shell lists, and which app it belongs to.
	const payload = (sidebars) =>
		Object.fromEntries(
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

	// Ask a question against a synthetic world, then put the real one back so the desk this spec
	// is running in survives.
	function ask(
		{ sidebars, canonical = {}, rail_hosts = {}, url_shell = null, on_screen = null },
		question
	) {
		cy.window().then((win) => {
			const frappe = win.frappe;
			const real = {
				module_sidebars: frappe.boot.module_sidebars,
				canonical_shell: frappe.boot.canonical_shell,
				app_rail_host: frappe.boot.app_rail_host,
				current_shell: frappe.router.current_shell,
			};

			frappe.boot.module_sidebars = payload(sidebars);
			frappe.boot.canonical_shell = { DocType: canonical };
			frappe.boot.app_rail_host = rail_hosts;
			frappe.router.current_shell = url_shell;

			// Neither question touches instance state beyond `current_module`, so this needs no
			// constructed sidebar.
			const sidebar = Object.create(win.frappe.ui.Sidebar.prototype);
			sidebar.current_module = on_screen;

			let answer;
			try {
				answer = question(sidebar);
			} finally {
				frappe.boot.module_sidebars = real.module_sidebars;
				frappe.boot.canonical_shell = real.canonical_shell;
				frappe.boot.app_rail_host = real.app_rail_host;
				frappe.router.current_shell = real.current_shell;
			}
			return answer;
		});
	}

	const can_show = (world, shell, route, expected) =>
		ask(world, (sidebar) => {
			expect(sidebar.shell_can_show(shell, route)).to.equal(expected);
		});

	context("a shell may show a route it lists", () => {
		const world = {
			sidebars: { Stock: ["Item"], Selling: ["Customer"] },
			canonical: { Item: "Stock", Customer: "Selling" },
		};

		it("lets a shell show what it lists", () => {
			can_show(world, "Selling", ["List", "Customer"], true);
		});

		it("refuses a shell this user does not have", () => {
			can_show(world, "Not A Shell", ["List", "Item"], false);
		});

		it("refuses a route that names no entity", () => {
			can_show(world, "Stock", [], false);
		});
	});

	context("the shell on screen holds inside its app, and only inside it", () => {
		// The shape measured on a site with erpnext and hrms. Accounts is where you are; Job
		// Applicant belongs to HR, which hrms owns.
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

		it("keeps the shell for a route inside the same app", () => {
			can_show(cross_app, "Accounts", ["List", "Sales Order"], true);
		});

		it("gives up the shell for a route that belongs to another app", () => {
			can_show(cross_app, "Accounts", ["List", "Job Applicant"], false);
		});

		it("keeps a cross-app entity the shell curates a link to", () => {
			// Why the boundary is not simply "the entity's app wins": a sidebar that lists a
			// foreign entity has said it belongs here, and that outranks where it was authored.
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

			can_show(curated, "Accounts", ["List", "Job Applicant"], true);
		});

		it("keeps the shell when a companion app mounts on the same rail", () => {
			// india_payroll has no rail of its own; its entries live on hrms's. Both sides resolve
			// through the host, so there is no boundary to cross.
			const companion = {
				sidebars: {
					HR: { links: ["Job Applicant"], app: "hrms" },
					"India Payroll": { links: ["Salary Slip"], app: "india_payroll" },
				},
				canonical: { "Job Applicant": "HR", "Salary Slip": "India Payroll" },
				rail_hosts: { india_payroll: "hrms" },
			};

			can_show(companion, "HR", ["List", "Salary Slip"], true);
		});

		it("keeps the shell when the entity belongs to no app", () => {
			// A shell an app never placed answers null for its app, and null is never equal to
			// one, so an unplaced module neither holds a shell nor moves one.
			const unplaced = {
				sidebars: {
					Accounts: { links: ["Journal Entry"], app: "erpnext" },
					Widgets: { links: ["Widget"] },
				},
				canonical: { "Journal Entry": "Accounts", Widget: "Widgets" },
			};

			can_show(unplaced, "Accounts", ["List", "Widget"], true);
		});
	});

	context("which shell a URL should name", () => {
		// Stock lists Item and Selling does not, and both are erpnext's, so either may show it.
		const world = {
			sidebars: {
				Stock: { links: ["Item"], app: "erpnext" },
				Selling: { links: ["Customer"], app: "erpnext" },
				HR: { links: ["Job Applicant"], app: "hrms" },
			},
			canonical: { Item: "Stock", Customer: "Selling", "Job Applicant": "HR" },
		};
		const route = ["List", "Item"];

		it("takes the shell the URL names", () => {
			// It has to outrank the sidebar on screen, or going back to a URL naming one shell
			// while standing in another would rewrite the entry it just returned to.
			ask({ ...world, url_shell: "Selling", on_screen: "HR" }, (sidebar) => {
				expect(sidebar.shell_for_route(route)).to.equal("Selling");
			});
		});

		it("falls to the shell on screen when the URL names none", () => {
			ask({ ...world, url_shell: null, on_screen: "Selling" }, (sidebar) => {
				expect(sidebar.shell_for_route(route)).to.equal("Selling");
			});
		});

		it("ignores a URL naming a shell that cannot show the route", () => {
			ask({ ...world, url_shell: "HR", on_screen: null }, (sidebar) => {
				expect(sidebar.shell_for_route(route)).to.equal("Stock");
			});
		});

		it("ignores a shell on screen that cannot show the route", () => {
			ask({ ...world, url_shell: null, on_screen: "HR" }, (sidebar) => {
				expect(sidebar.shell_for_route(route)).to.equal("Stock");
			});
		});

		it("falls to where the entity opens when nothing holds", () => {
			ask({ ...world, url_shell: null, on_screen: null }, (sidebar) => {
				expect(sidebar.shell_for_route(route)).to.equal("Stock");
			});
		});
	});

	// `default_shell` used to work the landing shell out here, from the user's own default
	// workspace. It does not any more: the server decides, with the same map it builds the rest
	// of the payload from (`home_shell` in sidebar.py, tested in test_sidebar.py), and sends the
	// answer down as `boot.home_shell`. What is left on this side is that the desk reads it.
	context("the route that names nothing", () => {
		it("lands on the home shell the server worked out", () => {
			cy.window().then((win) => {
				const sidebar = win.frappe.app.sidebar;
				const real = win.frappe.boot.home_shell;
				// Neither the home the server sent nor the first shell, which is the fallback
				// below. A shell that is either of those would be returned by a `default_shell`
				// that ignored `home_shell` entirely, and this would pass without asking
				// anything.
				const shells = Object.keys(win.frappe.boot.module_sidebars);
				const other = shells.find((shell) => shell !== real && shell !== shells[0]);

				expect(other, "no third shell here, so this test proves nothing").to.be.a(
					"string"
				);

				try {
					win.frappe.boot.home_shell = other;
					expect(sidebar.default_shell()).to.equal(other);
				} finally {
					win.frappe.boot.home_shell = real;
				}
			});
		});

		it("falls to the first shell on a boot that carries no home", () => {
			// Only for a desk loaded before the server began sending one. Every boot since has a
			// home shell, so this is the last resort and not the rule -- and the first shell is
			// the same for everyone, so two people who hit it land together.
			cy.window().then((win) => {
				const sidebar = win.frappe.app.sidebar;
				const real = win.frappe.boot.home_shell;

				try {
					win.frappe.boot.home_shell = null;
					expect(sidebar.default_shell()).to.equal(
						Object.keys(win.frappe.boot.module_sidebars)[0]
					);
				} finally {
					win.frappe.boot.home_shell = real;
				}
			});
		});
	});
});
