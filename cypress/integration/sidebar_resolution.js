// Cold-entry sidebar resolution: the order in resolve_initial_sidebar().
//
// Every case here is synthetic on purpose. No shipped fixture sets `is_default_module`, and the
// one worked example that will (hrms flagging `Employee`) lives in another app -- so the override
// can only be asserted against a payload this test writes. The scenarios below reproduce the shape
// measured on a site with erpnext and hrms installed: `Employee.module` is "Setup", Setup's sidebar
// does not list it, and HR Setup links it.
//
// The resolver reads boot data and localStorage and nothing else -- frappe.boot.module_sidebars,
// frappe.boot.entity_module, the three non-doctype maps DeskViews ships (allowed_reports,
// page_info, dashboards) and localStorage.selected_module -- which is why it can be exercised
// directly rather than through a navigation.
context("Cold-entry sidebar resolution", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/todo");
	});

	// An entity's home is decided against this payload; `items` only ever needs `link_to` here.
	const payload = (sidebars) =>
		Object.fromEntries(
			Object.entries(sidebars).map(([module, links]) => [
				module,
				{ module, items: links.map((link_to) => ({ link_to })) },
			])
		);

	// Resolve `route` against a synthetic world, restoring the real one afterwards so the desk this
	// spec is running in survives the test.
	function resolve(
		{
			sidebars,
			entity_module = {},
			metas = {},
			reports = {},
			pages = {},
			dashboards = [],
			heirs = {},
			persisted,
			route,
		},
		then
	) {
		cy.window().then((win) => {
			const frappe = win.frappe;
			const real = {
				module_sidebars: frappe.boot.module_sidebars,
				entity_module: frappe.boot.entity_module,
				allowed_reports: frappe.boot.allowed_reports,
				page_info: frappe.boot.page_info,
				dashboards: frappe.boot.dashboards,
				code_only_module_heirs: frappe.boot.code_only_module_heirs,
				get_meta: frappe.get_meta,
				selected_module: win.localStorage.getItem("selected_module"),
			};

			frappe.boot.module_sidebars = payload(sidebars);
			frappe.boot.entity_module = entity_module;
			frappe.boot.allowed_reports = reports;
			frappe.boot.page_info = pages;
			frappe.boot.dashboards = dashboards;
			frappe.boot.code_only_module_heirs = heirs;
			frappe.get_meta = (name) => metas[name] || null;
			if (persisted) win.localStorage.setItem("selected_module", persisted);
			else win.localStorage.removeItem("selected_module");

			// the resolver touches no instance state, so it needs no constructed sidebar
			const sidebar = Object.create(win.frappe.ui.Sidebar.prototype);
			let resolved;
			try {
				resolved = sidebar.resolve_initial_sidebar(route);
			} finally {
				frappe.boot.module_sidebars = real.module_sidebars;
				frappe.boot.entity_module = real.entity_module;
				frappe.boot.allowed_reports = real.allowed_reports;
				frappe.boot.page_info = real.page_info;
				frappe.boot.dashboards = real.dashboards;
				frappe.boot.code_only_module_heirs = real.code_only_module_heirs;
				frappe.get_meta = real.get_meta;
				if (real.selected_module) {
					win.localStorage.setItem("selected_module", real.selected_module);
				} else {
					win.localStorage.removeItem("selected_module");
				}
			}
			then(resolved);
		});
	}

	// Setup does not list Employee; HR Setup links it; Employee.module is "Setup".
	const employee_world = {
		sidebars: { Setup: ["Company", "Branch"], "HR Setup": ["Employee", "Company", "Branch"] },
		metas: { Employee: { module: "Setup" } },
		route: ["List", "Employee"],
	};

	it("takes the claim over the entity's own module when that module cannot show it", () => {
		resolve(
			{ ...employee_world, entity_module: { Employee: "HR Setup" }, persisted: "Setup" },
			(resolved) => {
				expect(resolved.sidebar).to.equal("HR Setup");
				expect(resolved.provisional).to.be.false;
			}
		);
	});

	// The claim confirms this answer rather than creating it -- the thing most likely to be broken
	// by a later change and never noticed, because the flagged fixture would mask it.
	it("demotes the entity's module to a link when the module does not list the entity", () => {
		resolve({ ...employee_world, persisted: "Setup" }, (resolved) => {
			expect(resolved.sidebar).to.equal("HR Setup");
			expect(resolved.provisional).to.be.false;
		});
	});

	it("keeps the sidebar you were in when it links the entity, even against a claim", () => {
		resolve(
			{
				sidebars: { Setup: ["Employee", "Company"], "HR Setup": ["Employee"] },
				metas: { Employee: { module: "Setup" } },
				entity_module: { Employee: "HR Setup" },
				persisted: "Setup",
				route: ["List", "Employee"],
			},
			(resolved) => {
				expect(resolved.sidebar).to.equal("Setup");
			}
		);
	});

	// The pair below is the entire contract of `is_default_module`, and no shipped fixture can state
	// it: hrms flags `Employee` in HR Setup, but erpnext's Setup does not list `Employee`, so the
	// demote already routes it and the flag changes nothing observable. What the flag buys is this
	// world -- the day Setup DOES list `Employee` -- so it is asserted against a payload written here.
	// Both cases run with no sticky at all, so step 1 is out of the way and step 2 is measured
	// against step 3 alone; the test above covers the sticky outranking both.
	const contested = {
		sidebars: { Setup: ["Employee", "Company"], "HR Setup": ["Employee"] },
		metas: { Employee: { module: "Setup" } },
		route: ["List", "Employee"],
	};

	it("takes the claim over the entity's own module even when that module lists the entity", () => {
		resolve({ ...contested, entity_module: { Employee: "HR Setup" } }, (resolved) => {
			expect(resolved.sidebar).to.equal("HR Setup");
			expect(resolved.provisional).to.be.false;
		});
	});

	it("gives the entity back to its own module when the claim is dropped", () => {
		resolve(contested, (resolved) => {
			expect(resolved.sidebar).to.equal("Setup");
			expect(resolved.provisional).to.be.false;
		});
	});

	it("does not keep a sidebar that does not link the entity", () => {
		resolve(
			{
				sidebars: { Website: ["Web Page"], "HR Setup": ["Employee"], Setup: ["Company"] },
				metas: { Employee: { module: "Setup" } },
				entity_module: { Employee: "HR Setup" },
				persisted: "Website",
				route: ["List", "Employee"],
			},
			(resolved) => {
				expect(resolved.sidebar).to.equal("HR Setup");
			}
		);
	});

	// `General Ledger` is a Report, so its module comes from frappe.boot.allowed_reports and never
	// from a meta -- stubbing get_meta for it (as this case originally did) describes a world the
	// desk cannot produce, and the answer was really coming from step 4. With the report map fed
	// honestly, step 3 decides it and the answer is final rather than provisional.
	it("keeps the entity's module ahead of a foreign sidebar when it does list the entity", () => {
		resolve(
			{
				sidebars: { Accounts: ["General Ledger"], Expenses: ["General Ledger"] },
				reports: { "General Ledger": { module: "Accounts" } },
				route: ["query-report", "General Ledger"],
			},
			(resolved) => {
				expect(resolved.sidebar).to.equal("Accounts");
				expect(resolved.provisional).to.be.false;
			}
		);
	});

	// The population this road exists for: 107 of the Reports, Pages and Dashboards on a site with
	// erpnext and hrms installed are linked in NO sidebar at all. Before their module was readable
	// they had no home rather than a bad one, and fell through to whichever sidebar sorted first.
	it("sends a report that no sidebar links to its own module", () => {
		resolve(
			{
				sidebars: { Accounts: ["General Ledger"], Stock: [] },
				reports: { "Stock Balance": { module: "Stock" } },
				route: ["query-report", "Stock Balance"],
			},
			(resolved) => {
				expect(resolved.sidebar).to.equal("Stock");
				expect(resolved.provisional).to.be.false;
			}
		);
	});

	it("sends a page that no sidebar links to its own module", () => {
		resolve(
			{
				sidebars: { Setup: ["Company"], Website: [] },
				pages: { "my-page": { module: "Website" } },
				route: ["my-page"],
			},
			(resolved) => {
				expect(resolved.sidebar).to.equal("Website");
				expect(resolved.provisional).to.be.false;
			}
		);
	});

	// The demote is the rule non-doctypes could never reach before: a module that cannot show the
	// entity yields to a sidebar that links it. `BOM Search` is the shipped example -- defined in
	// Stock, listed only by Manufacturing.
	it("demotes a report's own module when that module does not list it", () => {
		resolve(
			{
				sidebars: { Stock: ["Item"], Manufacturing: ["BOM Search"] },
				reports: { "BOM Search": { module: "Stock" } },
				route: ["query-report", "BOM Search"],
			},
			(resolved) => {
				expect(resolved.sidebar).to.equal("Manufacturing");
				expect(resolved.provisional).to.be.false;
			}
		);
	});

	// Entity names are not unique across kinds, so the module lookup is selected by the route rather
	// than probed. `Attendance` is real -- an hrms Dashboard in "Shift and Attendance" and an hrms
	// DocType in "HR" -- but hrms-only, so it is staged here. `dashboard-view` sits in page_info
	// because it genuinely is a Page: that is the shadow entity_from_route steps around, and without
	// it every dashboard route resolved as the page rather than as the dashboard.
	const attendance_world = {
		sidebars: { HR: ["Attendance"], "Shift and Attendance": ["Attendance"] },
		metas: { Attendance: { module: "HR" } },
		dashboards: [{ name: "Attendance", module: "Shift and Attendance" }],
		pages: { "dashboard-view": { module: "Core" } },
	};

	it("resolves a doctype and a dashboard of the same name to different modules", () => {
		resolve({ ...attendance_world, route: ["List", "Attendance"] }, (resolved) => {
			expect(resolved.sidebar).to.equal("HR");
		});
		resolve({ ...attendance_world, route: ["dashboard-view", "Attendance"] }, (resolved) => {
			expect(resolved.sidebar).to.equal("Shift and Attendance");
		});
	});

	// Step 3b: a standalone doctype is linked by nothing, so a plain membership test would drop it
	// into the sticky/first-available fallbacks instead of its own module.
	it("falls back to the entity's own module when no sidebar links the entity at all", () => {
		resolve(
			{
				sidebars: { Setup: ["Company"], "Custom Module": [] },
				metas: { "My Custom Doctype": { module: "Custom Module" } },
				persisted: "Setup",
				route: ["List", "My Custom Doctype"],
			},
			(resolved) => {
				expect(resolved.sidebar).to.equal("Custom Module");
				expect(resolved.provisional).to.be.false;
			}
		);
	});

	// The first pass of a cold load runs before the routed doctype's meta arrives, so the answer is
	// marked provisional and set_workspace_sidebar re-resolves it. Without the flag the module would
	// never get a look in.
	it("marks a link-only answer provisional while the meta is unread", () => {
		resolve(
			{
				sidebars: { Setup: ["Company"], "HR Setup": ["Employee"] },
				metas: {},
				route: ["List", "Employee"],
			},
			(resolved) => {
				expect(resolved.sidebar).to.equal("HR Setup");
				expect(resolved.provisional).to.be.true;
			}
		);
	});

	// The one thing hrms's shipped flag does change. Without it `Employee` is a step-4 answer, and
	// step 4 is provisional while the meta is unread, so a cold deep link resolves twice and lands in
	// HR Setup both times. With it the first pass is final -- same shell, one pass. Step 2 reads boot
	// data only, so it never has to wait for a meta.
	it("answers finally on the first pass when the entity is claimed, meta or no meta", () => {
		resolve(
			{
				sidebars: { Setup: ["Company"], "HR Setup": ["Employee"] },
				metas: {},
				entity_module: { Employee: "HR Setup" },
				route: ["List", "Employee"],
			},
			(resolved) => {
				expect(resolved.sidebar).to.equal("HR Setup");
				expect(resolved.provisional).to.be.false;
			}
		);
	});

	// A code-only module ships no navigation, so it is absent from the payload and its entities used
	// to dead-end: `User`, `System Settings` and `permission-manager` are all `Core`, and all three
	// open in erpnext's `Setup` on every erpnext site because erpnext curated a link and frappe's
	// side of the split was unstated. The heir map states it, and membership picks within it.
	//
	// The heir order below is frappe's own, and it is read twice -- it breaks ties among heirs that
	// both list the entity, and it names the home for an entity none of them lists.
	const code_only_world = {
		sidebars: {
			"Build Tools": ["Module Def", "Translation", "Client Script"],
			Data: ["Data Import"],
			Email: ["Communication"],
			Setup: [
				"User",
				"System Settings",
				"permission-manager",
				"Deleted Document",
				"Company",
			],
			System: ["System Settings", "Module Def", "Translation", "Log Settings"],
			Users: ["User", "permission-manager", "Role"],
		},
		metas: {
			User: { module: "Core" },
			"System Settings": { module: "Core" },
			"Module Def": { module: "Core" },
			"Prepared Report": { module: "Core" },
			"Deleted Document": { module: "Core" },
		},
		pages: { "permission-manager": { module: "Core" } },
		heirs: {
			Core: ["System", "Build Tools", "Data", "Users", "Email"],
			Custom: ["Build Tools"],
			Desk: ["Build Tools"],
		},
	};

	// The three that move on a real site. The STEP matters as much as the answer: an heir that lists
	// the entity has to win at step 3, because step 4 is where erpnext's Setup was taking them.
	[
		[["List", "User"], "Users"],
		[["List", "System Settings"], "System"],
		[["permission-manager"], "Users"],
	].forEach(([route, expected]) => {
		it(`sends ${route.join("/")} to the heir that lists it (${expected}), at step 3`, () => {
			resolve({ ...code_only_world, route }, (resolved) => {
				expect(resolved.sidebar).to.equal(expected);
				expect(resolved.reason).to.contain("and it lists the entity");
				expect(resolved.provisional).to.be.false;
			});
		});
	});

	// Both System and Build Tools list `Module Def`; the declaration order decides, which is why the
	// hook is a list and appending to it is a decision rather than a transcription.
	it("breaks a tie between two listing heirs by declaration order", () => {
		resolve({ ...code_only_world, route: ["List", "Module Def"] }, (resolved) => {
			expect(resolved.sidebar).to.equal("System");
			expect(resolved.reason).to.contain("and it lists the entity");
		});
	});

	// The ~40 internals nothing links anywhere. They used to land on the sticky or on whatever
	// sidebar sorted first; the first declared heir is the same "last principled answer" 3b already
	// gives a standalone doctype.
	it("sends a code-only entity that nothing links to the first heir, via 3b", () => {
		resolve(
			{ ...code_only_world, persisted: "Setup", route: ["List", "Prepared Report"] },
			(resolved) => {
				expect(resolved.sidebar).to.equal("System");
				expect(resolved.reason).to.contain("no sidebar links the entity at all");
			}
		);
	});

	// The payload is permission-filtered, so "first heir" means first heir THIS user has. Two users
	// can correctly land in different shells for the same entity -- ownership is per-user.
	it("skips an heir this user cannot see and takes the next", () => {
		const { System, ...without_system } = code_only_world.sidebars;
		resolve(
			{
				...code_only_world,
				sidebars: without_system,
				persisted: "Setup",
				route: ["List", "Prepared Report"],
			},
			(resolved) => {
				expect(resolved.sidebar).to.equal("Build Tools");
				expect(resolved.reason).to.contain("no sidebar links the entity at all");
			}
		);
	});

	// The heirs get no exception from the map's one rule. A sidebar that can actually show you the
	// entity beats a shell that merely inherited the module, so step 4 still runs before 3b. No
	// shipped row exercises this today, which is why it is asserted here rather than measured.
	it("lets a foreign link beat the default heir", () => {
		resolve({ ...code_only_world, route: ["List", "Deleted Document"] }, (resolved) => {
			expect(resolved.sidebar).to.equal("Setup");
			expect(resolved.reason).to.contain("is not listed by its own module's sidebar");
		});
	});

	// cold_entry_needs_recheck is deliberately broader than step 3's gate: it fires whenever the
	// module became readable, including when that module cannot show the entity -- which is exactly
	// the case the second pass exists for.
	it("fires the second pass for an entity its own module does not list", () => {
		cy.window().then((win) => {
			const frappe = win.frappe;
			const real_get_meta = frappe.get_meta;
			const real_sidebars = frappe.boot.module_sidebars;

			frappe.boot.module_sidebars = payload({ Setup: [], "HR Setup": ["Employee"] });
			frappe.get_meta = (name) => (name === "Employee" ? { module: "Setup" } : null);

			const sidebar = Object.create(win.frappe.ui.Sidebar.prototype);
			sidebar.pending_cold_entry = "List/Employee";
			try {
				expect(sidebar.cold_entry_needs_recheck(["List", "Employee"], "Employee")).to.be
					.true;
			} finally {
				frappe.get_meta = real_get_meta;
				frappe.boot.module_sidebars = real_sidebars;
			}
		});
	});
});
