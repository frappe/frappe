import child_table_with_collapsible_section from "../fixtures/child_table_with_collapsible_section";
import doctype_with_collapsible_child_section from "../fixtures/doctype_with_collapsible_child_section";

const parent_doctype_name = doctype_with_collapsible_child_section.name;

context("Form Section Collapse Indicator", () => {
	const open_section = () => {
		cy.fill_field("title", "Test Document");

		cy.get('.frappe-control[data-fieldname="items"]').as("table");
		cy.get("@table").findByRole("button", { name: "Add row" }).click();
		cy.get("@table").find('[data-idx="1"]').find(".btn-open-row").click();
		cy.get(".grid-row-open")
			.find('.form-section[data-fieldname="details_section"]')
			.as("section");
	};

	before(() => {
		cy.login();
		cy.visit("/desk/website");
		return cy.insert_doc("DocType", child_table_with_collapsible_section, true).then(() => {
			return cy.insert_doc("DocType", doctype_with_collapsible_child_section, true);
		});
	});

	after(() => {
		cy.window()
			.its("frappe.user.name")
			.then((user) => cy.set_value("User", user, { language: "en" }));
	});

	beforeEach(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.new_form(parent_doctype_name);
		open_section();
	});

	const expect_indicator = (icon) => {
		cy.get("@section")
			.find(".collapse-indicator use")
			.should("have.attr", "href", `#icon-${icon}`);
	};

	it("uses the correct collapse indicator in LTR", () => {
		cy.get("@section").find(".section-body").should("have.class", "hide");
		expect_indicator("chevron-right");

		cy.get("@section").find(".section-head").click();
		cy.get("@section").find(".section-body").should("not.have.class", "hide");
		expect_indicator("chevron-down");

		cy.get("@section").find(".section-head").click();
		cy.get("@section").find(".section-body").should("have.class", "hide");
		expect_indicator("chevron-right");
	});

	it("uses the correct collapse indicator in RTL", () => {
		cy.window()
			.its("frappe.user.name")
			.then((user) => cy.set_value("User", user, { language: "ar" }))
			.then(() => cy.new_form(parent_doctype_name))
			.then(open_section);

		cy.get("html").should("have.attr", "dir", "rtl");
		cy.get("@section").find(".section-body").should("have.class", "hide");
		expect_indicator("chevron-left");

		cy.get("@section").find(".section-head").click();
		cy.get("@section").find(".section-body").should("not.have.class", "hide");
		expect_indicator("chevron-down");

		cy.get("@section").find(".section-head").click();
		cy.get("@section").find(".section-body").should("have.class", "hide");
		expect_indicator("chevron-left");
	});
});
