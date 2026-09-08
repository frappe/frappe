import child_table_with_collapsible_section from "../fixtures/child_table_with_collapsible_section";
import doctype_with_collapsible_child_section from "../fixtures/doctype_with_collapsible_child_section";

const parent_doctype_name = doctype_with_collapsible_child_section.name;

context("Grid Row Form Section Collapse", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		return cy.insert_doc("DocType", child_table_with_collapsible_section, true).then(() => {
			return cy.insert_doc("DocType", doctype_with_collapsible_child_section, true);
		});
	});

	beforeEach(() => {
		cy.login();
		cy.visit("/desk/website");

		cy.new_form(parent_doctype_name);
		cy.fill_field("title", "Test Document");

		cy.get('.frappe-control[data-fieldname="items"]').as("table");
		cy.get("@table").findByRole("button", { name: "Add Row" }).click();
		cy.get("@table").find('[data-idx="1"]').find(".btn-open-row").click();

		cy.get(".grid-row-open").as("row-form");
		cy.get("@row-form").find('.form-section[data-fieldname="details_section"]').as("section");
		cy.get("@row-form")
			.find('.frappe-control[data-fieldname="description"] textarea')
			.as("description");
	});

	// `notes` depends on `description`, so it turns visible only once the row has
	// been refreshed — without waiting for it the assertions below race the refresh.
	const type_description = () => {
		cy.get("@description").type("Hello").blur();
		cy.get("@row-form").find('.frappe-control[data-fieldname="notes"]').should("be.visible");
	};

	it("collapses the section until the user opens it", () => {
		cy.get("@section").find(".section-body").should("have.class", "hide");
	});

	it("keeps the section open while typing in a field inside it", () => {
		cy.get("@section").find(".section-head").click();
		cy.get("@section").find(".section-body").should("not.have.class", "hide");

		type_description();

		cy.get("@section").find(".section-body").should("not.have.class", "hide");
		cy.get("@description").should("have.value", "Hello");
	});

	it("keeps the section collapsed after the user closes it", () => {
		cy.get("@section").find(".section-head").click();
		type_description();
		cy.get("@section").find(".section-head").click();
		cy.get("@section").find(".section-body").should("have.class", "hide");

		cy.window().its("cur_frm").invoke("refresh_fields");

		cy.get("@section").find(".section-body").should("have.class", "hide");
	});

	it("collapses the section again when the row form is reopened", () => {
		cy.get("@section").find(".section-head").click();
		cy.get("@section").find(".section-body").should("not.have.class", "hide");

		cy.get("@row-form").find(".grid-collapse-row").click();
		cy.get("@table").find('[data-idx="1"]').find(".btn-open-row").click();

		cy.get(".grid-row-open")
			.find('.form-section[data-fieldname="details_section"] .section-body')
			.should("have.class", "hide");
	});
});
