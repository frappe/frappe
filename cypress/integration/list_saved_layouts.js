const LIST_URL = "/desk/todo";

// saved layouts live in the view switcher now: the current view's row
// ("List View") carries them as an async submenu
function openLayoutSubmenu() {
	cy.get(".custom-btn-group.view-switcher button").click();
	cy.contains(".es-menu__item", "List View").trigger("pointerenter");
	// the submenu lazy-loads the layouts bundle — wait for its rows
	cy.contains(".es-menu__item", "Default Layout").should("exist");
}

function closeMenus() {
	cy.focused().trigger("keydown", { key: "Escape" });
	cy.get(".es-menu[data-state='open']").should("not.exist");
}

function selectLayout(label) {
	openLayoutSubmenu();
	cy.contains(".es-menu__item", label).click();
	cy.wait(500);
}

// the switcher trigger shows the active layout name (or "List View" when
// the default layout is active)
function assertActiveLayout(label) {
	const trigger_label = label === "Default Layout" ? "List View" : label;
	cy.get(".custom-btn-group.view-switcher button").should("contain", trigger_label);
}

function clearTestLayouts() {
	return cy.call("frappe.tests.ui_test_helpers.clear_list_layout_test_layouts");
}

function resetLayoutUserSettings() {
	return cy.call("frappe.tests.ui_test_helpers.reset_list_layout_test_user_settings");
}

function createTestLayout(args = {}) {
	return cy.call("frappe.tests.ui_test_helpers.create_list_layout_test_layout", args);
}

context("List View — Saved Layouts", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
	});

	beforeEach(() => {
		clearTestLayouts();
		resetLayoutUserSettings();
		cy.visit("/desk/website");
	});

	it("shows default layout and action rows in the menu", () => {
		cy.visit(LIST_URL);
		cy.desk_ready();
		cy.clear_filters();

		openLayoutSubmenu();
		cy.contains(".es-menu__item", "Default Layout").should("be.visible");
		cy.contains(".es-menu__item", "Create Layout").should("be.visible");
		cy.contains(".es-menu__item", "Manage Layouts").should("be.visible");
		closeMenus();
	});

	it("restores last selected layout on a clean URL when no URL filters exist", () => {
		createTestLayout({
			layout_name: "_cypress_layout_empty",
			filters: "[]",
		});

		cy.visit(LIST_URL);
		cy.desk_ready();
		cy.clear_filters();

		selectLayout("_cypress_layout_empty");
		assertActiveLayout("_cypress_layout_empty");

		cy.visit(LIST_URL);
		cy.desk_ready();
		cy.clear_filters();

		assertActiveLayout("_cypress_layout_empty");
	});

	it("does not auto-apply empty-filter layout from URL signature alone", () => {
		createTestLayout({
			layout_name: "_cypress_layout_empty",
			filters: "[]",
		});

		cy.visit(LIST_URL);
		cy.desk_ready();
		cy.clear_filters();

		assertActiveLayout("Default Layout");
	});

	it("auto-applies a layout when the URL matches its route signature", () => {
		createTestLayout({
			layout_name: "_cypress_layout_open",
			filters: JSON.stringify([["ToDo", "status", "=", "Open"]]),
			route_signature: "status=Open",
		});

		cy.visit(`${LIST_URL}?status=Open`);
		cy.desk_ready();

		assertActiveLayout("_cypress_layout_open");
	});

	it("applies a saved layout from the menu and can switch back to default", () => {
		createTestLayout({
			layout_name: "_cypress_layout_switch",
			filters: JSON.stringify([["ToDo", "status", "=", "Open"]]),
			route_signature: "status=Open",
		});

		cy.visit(LIST_URL);
		cy.desk_ready();
		cy.clear_filters();

		selectLayout("_cypress_layout_switch");
		assertActiveLayout("_cypress_layout_switch");

		selectLayout("Default Layout");
		assertActiveLayout("Default Layout");
	});

	it("opens manage layouts dialog with the saved layout listed", () => {
		createTestLayout({
			layout_name: "_cypress_layout_manage",
		});

		cy.visit(LIST_URL);
		cy.desk_ready();

		openLayoutSubmenu();
		cy.contains(".es-menu__item", "Manage Layouts").click();

		cy.get(".modal-dialog").should("contain", "Manage Layouts");
		cy.get(".layout-manage-row").should("contain", "_cypress_layout_manage");
		cy.get(".layout-manage-row").should("contain", "Personal");
	});

	it("switches to list view with a layout applied, from another view", () => {
		createTestLayout({
			layout_name: "_cypress_layout_jump",
			filters: JSON.stringify([["ToDo", "status", "=", "Open"]]),
			route_signature: "status=Open",
		});

		cy.visit(`${LIST_URL}/view/report`);
		cy.wait(500);

		// the List row hosts the layouts as an async submenu from other views
		cy.get(".custom-btn-group.view-switcher button").click();
		cy.contains(".es-menu__item", "List View").trigger("pointerenter");
		cy.contains(".es-menu__item", "_cypress_layout_jump").click();

		// one click: switched AND applied (preference + clean route + restore)
		cy.window()
			.its("cur_list")
			.should((list) => {
				expect(list.view_name).to.equal("List");
			});
		assertActiveLayout("_cypress_layout_jump");
	});

	it("fetches non-in_list_view fields used as saved layout columns", () => {
		// `role` is on ToDo but not in_list_view — layout columns must still be fetched.
		createTestLayout({
			layout_name: "_cypress_layout_columns",
			filters: "[]",
			columns: JSON.stringify([
				{ fieldname: "description", label: "Description" },
				{ fieldname: "status_field", label: "Status" },
				{ fieldname: "role", label: "Role" },
			]),
		});
		createTestLayout({
			layout_name: "_cypress_layout_no_role",
			filters: "[]",
			columns: JSON.stringify([
				{ fieldname: "description", label: "Description" },
				{ fieldname: "status_field", label: "Status" },
				{ fieldname: "priority", label: "Priority" },
			]),
		});

		cy.visit(LIST_URL);
		cy.wait(500);
		cy.clear_filters();

		selectLayout("_cypress_layout_columns");
		assertActiveLayout("_cypress_layout_columns");

		cy.window().then((win) => {
			const list = win.cur_list;
			expect(list).to.exist;

			const fetch_fields = (list.fields || []).map((f) => f[0]);
			expect(fetch_fields).to.include("role");

			const column_names = (list.columns || [])
				.filter((col) => col.df?.fieldname)
				.map((col) => col.df.fieldname);
			expect(column_names).to.include("role");
		});

		// Switching layouts should drop fields that are no longer visible.
		selectLayout("_cypress_layout_no_role");
		assertActiveLayout("_cypress_layout_no_role");

		cy.window().then((win) => {
			const fetch_fields = (win.cur_list.fields || []).map((f) => f[0]);
			expect(fetch_fields).to.not.include("role");
			expect(fetch_fields).to.include("priority");
		});
	});
});
