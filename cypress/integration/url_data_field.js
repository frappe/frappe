import data_field_validation_doctype from "../fixtures/data_field_validation_doctype";

const doctype_name = data_field_validation_doctype.name;

context("URL Data Field Input", () => {
	before(() => {
		cy.login();
		cy.visit("/app/website");
		return cy.insert_doc("DocType", data_field_validation_doctype, true);
	});

	describe("URL Data Field Input ", () => {
		it("should not show URL link button without focus", () => {
			cy.new_form(doctype_name);
			cy.get_field("url").clear().type("https://frappe.io");
			cy.get_field("url").blur().wait(500);
			cy.get(".link-btn").should("not.be.visible");
		});

		it("should show URL link button on focus", () => {
			cy.get_field("url").focus().wait(500);
			cy.get(".link-btn").should("be.visible");
		});

		it("should not show URL link button for invalid URL", () => {
			cy.get_field("url").clear().type("fuzzbuzz");
			cy.get(".link-btn").should("not.be.visible");
		});

		it("should have valid URL link with target _blank", () => {
			cy.get_field("url").clear().type("https://frappe.io");
			cy.get(".link-btn .btn-open").should("have.attr", "href", "https://frappe.io");
			cy.get(".link-btn .btn-open").should("have.attr", "target", "_blank");
		});

		it("should inject anchor tag in read-only URL data field", () => {
			cy.get('[data-fieldname="read_only_url"]')
				.find("a")
				.should("have.attr", "target", "_blank");
		});
	});
});
