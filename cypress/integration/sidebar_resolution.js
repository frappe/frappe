// Cold-entry sidebar resolution: the order in resolve_initial_sidebar().
//
// Every case here is synthetic on purpose. No shipped fixture sets `is_default_module`, and the
// one worked example that will (hrms flagging `Employee`) lives in another app -- so the override
// can only be asserted against a payload this test writes. The scenarios below reproduce the shape
// measured on a site with erpnext and hrms installed: `Employee.module` is "Setup", Setup's sidebar
// does not list it, and HR Setup links it.
//
// The resolver reads three things and nothing else -- frappe.boot.module_sidebars,
// frappe.boot.entity_module and localStorage.selected_module -- which is why it can be exercised
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
	function resolve({ sidebars, entity_module = {}, metas = {}, persisted, route }, then) {
		cy.window().then((win) => {
			const frappe = win.frappe;
			const real = {
				module_sidebars: frappe.boot.module_sidebars,
				entity_module: frappe.boot.entity_module,
				get_meta: frappe.get_meta,
				selected_module: win.localStorage.getItem("selected_module"),
			};

			frappe.boot.module_sidebars = payload(sidebars);
			frappe.boot.entity_module = entity_module;
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

	it("keeps the entity's module ahead of a foreign sidebar when it does list the entity", () => {
		resolve(
			{
				sidebars: { Accounts: ["General Ledger"], Expenses: ["General Ledger"] },
				metas: { "General Ledger": { module: "Accounts" } },
				route: ["query-report", "General Ledger"],
			},
			(resolved) => {
				expect(resolved.sidebar).to.equal("Accounts");
			}
		);
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
