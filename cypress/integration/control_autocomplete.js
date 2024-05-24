context("Control Autocomplete", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
	});

	function get_dialog_with_autocomplete(options) {
		cy.visit("/app");
		cy.wait(1000); // wait for the workspace to load

		return cy.dialog({
			title: "Autocomplete",
			fields: [
				{
					label: "Select an option",
					fieldname: "autocomplete",
					fieldtype: "Autocomplete",
					options: options || ["Option 1", "Option 2", "Option 3"],
				},
			],
		});
	}

	it("should set the valid value", () => {
		get_dialog_with_autocomplete().as("dialog");

		cy.get(".frappe-control[data-fieldname=autocomplete] input").as("input");
		cy.get("@input").focus();
		cy.get(".frappe-control[data-fieldname=autocomplete]")
			.findByRole("listbox")
			.should("be.visible");
		cy.get("@input").type("2", { delay: 300 }).type("{enter}", { delay: 300 });
		cy.wait(500);
		cy.get("@input").blur();
		cy.get("@dialog").then((dialog) => {
			let value = dialog.get_value("autocomplete");
			expect(value).to.eq("Option 2");
			dialog.clear();
		});
	});

	it("should set the valid value with different label", () => {
		const options_with_label = [
			{ label: "Option 1", value: "option_1" },
			{ label: "Option 2", value: "option_2" },
		];
		get_dialog_with_autocomplete(options_with_label).as("dialog");

		cy.get(".frappe-control[data-fieldname=autocomplete] input").as("input");
		cy.get("@input").focus();
		cy.get(".frappe-control[data-fieldname=autocomplete]")
			.findByRole("listbox")
			.should("be.visible");
		cy.get("@input").type("2{enter}", { delay: 300 }).blur();
		cy.get("@dialog").then((dialog) => {
			let value = dialog.get_value("autocomplete");
			expect(value).to.eq("option_2");
			dialog.clear();
		});
	});
});
