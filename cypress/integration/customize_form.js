context("Customize Form", () => {
	before(() => {
		cy.login();
		cy.visit("/app/customize-form");
	});
	it("Changing to naming rule should update autoname", () => {
		cy.fill_field("doc_type", "ToDo", "Link").blur();
		cy.click_form_section("Naming");
		const naming_rule_default_autoname_map = {
			"Set by user": "prompt",
			"By fieldname": "field:",
			'By "Naming Series" field': "naming_series:",
			Expression: "format:",
			"Expression (old style)": "",
			Random: "hash",
			"By script": "",
		};
		Cypress._.forOwn(naming_rule_default_autoname_map, (value, naming_rule) => {
			cy.fill_field("naming_rule", naming_rule, "Select");
			cy.get_field("autoname", "Data").should("have.value", value);
		});
	});
});
