// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
// License: MIT. See LICENSE

context("Advanced Filters", () => {
	before(() => {
		cy.login();
		// Three ToDos with distinct, easily-asserted descriptions and priorities.
		cy.insert_doc("ToDo", { description: "AF alpha", priority: "High", status: "Open" }, true);
		cy.insert_doc("ToDo", { description: "AF beta", priority: "Low", status: "Open" }, true);
		cy.insert_doc("ToDo", { description: "AF gamma", priority: "Medium", status: "Closed" }, true);
	});

	beforeEach(() => {
		cy.login();
		cy.go_to_list("ToDo");
		cy.clear_filters();
	});

	// --- helpers -----------------------------------------------------------------

	const open_advanced = () => {
		cy.open_list_filter();
		cy.get(".advanced-filter-link").click();
		cy.get(".advanced-filter").should("be.visible");
	};

	// Pick a field in a rule's field picker (a frappe.ui.FieldSelect awesomplete).
	const set_field = (ruleIndex, label) => {
		cy.get(".filter-rule")
			.eq(ruleIndex)
			.find(".filter-rule-field input")
			.clear({ force: true })
			.type(label, { force: true });
		cy.get(".awesomplete li").contains(new RegExp(`^${label}$`)).click();
	};

	const set_operator = (ruleIndex, value) => {
		cy.get(".filter-rule").eq(ruleIndex).find(".filter-rule-operator").select(value);
	};

	const set_select_value = (ruleIndex, value) => {
		cy.get(".filter-rule").eq(ruleIndex).find(".filter-rule-value select").select(value);
	};

	const apply = () => {
		cy.get(".advanced-filter .btn-primary").contains("Apply").click();
	};

	// --- specs -------------------------------------------------------------------

	it("opens via the 'Use advanced filtering' link", () => {
		open_advanced();
		cy.get(".filter-rule").should("have.length.at.least", 1);
	});

	it("applies a single rule and filters the list", () => {
		open_advanced();
		set_field(0, "Status");
		set_select_value(0, "Closed");
		apply();

		cy.get(".list-row-container").should("contain", "AF gamma");
		cy.get(".list-row-container").should("not.contain", "AF alpha");
		// The toolbar reflects that an advanced filter is active.
		cy.get(".filter-button .button-label").should("contain", "Advanced Filter");
	});

	it("supports an OR across rules", () => {
		open_advanced();
		set_field(0, "Priority");
		set_select_value(0, "High");

		// Add a second rule and switch the group conjunction to Or.
		cy.get(".add-rule").first().click();
		cy.get(".conjunction-select").select("or");
		set_field(1, "Priority");
		set_select_value(1, "Low");
		apply();

		// High OR Low -> alpha and beta, but not the Medium gamma.
		cy.get(".list-row-container").should("contain", "AF alpha");
		cy.get(".list-row-container").should("contain", "AF beta");
		cy.get(".list-row-container").should("not.contain", "AF gamma");
	});

	it("supports a nested group", () => {
		// (status = Open) AND (priority = High OR priority = Low)
		open_advanced();
		set_field(0, "Status");
		set_select_value(0, "Open");

		cy.get(".add-group").first().click();
		// The nested group renders its own rules; target the group's first child rule.
		cy.get(".nested-group .filter-rule").should("exist");
		// Configure the two rules inside the nested group via their global rule index.
		set_field(1, "Priority");
		set_select_value(1, "High");
		cy.get(".nested-group .add-rule").first().click();
		cy.get(".nested-group .conjunction-select").select("or");
		set_field(2, "Priority");
		set_select_value(2, "Low");
		apply();

		cy.get(".list-row-container").should("contain", "AF alpha"); // Open + High
		cy.get(".list-row-container").should("contain", "AF beta"); // Open + Low
		cy.get(".list-row-container").should("not.contain", "AF gamma"); // Closed
	});

	it("round-trips: the advanced filter survives a reload", () => {
		open_advanced();
		set_field(0, "Status");
		set_select_value(0, "Closed");
		apply();
		cy.get(".list-row-container").should("contain", "AF gamma");

		cy.reload();
		cy.get(".filter-button .button-label").should("contain", "Advanced Filter");
		cy.get(".list-row-container").should("contain", "AF gamma");
		cy.get(".list-row-container").should("not.contain", "AF alpha");
	});

	it("clears the advanced filter", () => {
		open_advanced();
		set_field(0, "Status");
		set_select_value(0, "Closed");
		apply();
		cy.get(".filter-button .button-label").should("contain", "Advanced Filter");

		cy.open_list_filter();
		cy.get(".advanced-filter-link").click();
		cy.get(".advanced-filter .btn-secondary").contains("Clear").click();

		cy.get(".filter-button .button-label").should("not.contain", "Advanced Filter");
		cy.get(".list-row-container").should("contain", "AF alpha");
	});
});
