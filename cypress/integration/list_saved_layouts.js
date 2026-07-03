const LIST_URL = "/desk/todo";
const LAYOUT_GROUP = encodeURIComponent("Default Layout");

function openSavedLayoutsMenu() {
	cy.get(`.inner-group-button[data-label="${LAYOUT_GROUP}"] > button`).click({ force: true });
}

function getLayoutButton() {
	return cy.get(`.inner-group-button[data-label="${LAYOUT_GROUP}"] > button`);
}

function selectLayout(label) {
	openSavedLayoutsMenu();
	cy.get(".saved-filter-item .filter-label").contains(label).click();
	cy.wait(500);
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
		cy.wait(500);
		cy.clear_filters();

		openSavedLayoutsMenu();
		cy.get(".saved-filter-item .filter-label").should("contain", "Default Layout");
		cy.get(".saved-layout-action-item").contains("Create Layout").should("be.visible");
		cy.get(".saved-layout-action-item").contains("Manage Layouts").should("be.visible");
	});

	it("restores last selected layout on a clean URL when no URL filters exist", () => {
		createTestLayout({
			layout_name: "_cypress_layout_empty",
			filters: "[]",
		});

		cy.visit(LIST_URL);
		cy.wait(500);
		cy.clear_filters();

		selectLayout("_cypress_layout_empty");
		getLayoutButton().should("contain", "_cypress_layout_empty");

		cy.visit(LIST_URL);
		cy.wait(1000);
		cy.clear_filters();

		getLayoutButton().should("contain", "_cypress_layout_empty");
	});

	it("does not auto-apply empty-filter layout from URL signature alone", () => {
		createTestLayout({
			layout_name: "_cypress_layout_empty",
			filters: "[]",
		});

		cy.visit(LIST_URL);
		cy.wait(1000);
		cy.clear_filters();

		getLayoutButton().should("contain", "Default Layout");
	});

	it("auto-applies a layout when the URL matches its route signature", () => {
		createTestLayout({
			layout_name: "_cypress_layout_open",
			filters: JSON.stringify([["ToDo", "status", "=", "Open"]]),
			route_signature: "status=Open",
		});

		cy.visit(`${LIST_URL}?status=Open`);
		cy.wait(1000);

		getLayoutButton().should("contain", "_cypress_layout_open");
	});

	it("applies a saved layout from the menu and can switch back to default", () => {
		createTestLayout({
			layout_name: "_cypress_layout_switch",
			filters: JSON.stringify([["ToDo", "status", "=", "Open"]]),
			route_signature: "status=Open",
		});

		cy.visit(LIST_URL);
		cy.wait(500);
		cy.clear_filters();

		selectLayout("_cypress_layout_switch");
		getLayoutButton().should("contain", "_cypress_layout_switch");

		selectLayout("Default Layout");
		getLayoutButton().should("contain", "Default Layout");
	});

	it("opens manage layouts dialog with the saved layout listed", () => {
		createTestLayout({
			layout_name: "_cypress_layout_manage",
		});

		cy.visit(LIST_URL);
		cy.wait(500);

		openSavedLayoutsMenu();
		cy.get(".saved-layout-action-item").contains("Manage Layouts").click();

		cy.get(".modal-dialog").should("contain", "Manage Layouts");
		cy.get(".layout-manage-row").should("contain", "_cypress_layout_manage");
		cy.get(".layout-manage-row").should("contain", "Personal");
	});
});
