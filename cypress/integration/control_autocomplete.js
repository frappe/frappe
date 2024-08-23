context("Control Autocomplete", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
		cy.wait(4000);
	});

	const get_dialog_with_autocomplete = (fieldname, options) => {
		return cy.dialog({
			title: "Autocomplete",
			fields: [
				{
					label: "Select an option",
					fieldname: fieldname,
					fieldtype: "Autocomplete",
					options: options,
				},
			],
		});
	};

	it("should set the valid value", () => {
		const fieldname = "autocomplete_1";
		get_dialog_with_autocomplete(fieldname, ["Option 1", "Option 2", "Option 3"]).as("dialog");
		cy.get(`.control-input > .awesomplete > input[data-fieldname=${fieldname}]`).as("input");
		cy.wait(500);
		cy.get("@input").type("2{enter}", { delay: 300 });
		cy.get("@dialog").then((dialog) => {
			let value = dialog.get_value(fieldname);
			expect(value).to.eq("Option 2");
			dialog.clear();
			dialog.hide();
		});
	});

	it("should set the valid value with different label", () => {
		const fieldname = "autocomplete_2";
		get_dialog_with_autocomplete(fieldname, [
			{ label: "Option 1", value: "option_1" },
			{ label: "Option 2", value: "option_2" },
		]).as("dialog");

		cy.get(`.control-input > .awesomplete > input[data-fieldname=${fieldname}]`).as("input");
		cy.wait(500);
		cy.get("@input").type("2{enter}", { delay: 300 });
		cy.get("@dialog").then((dialog) => {
			let value = dialog.get_value(fieldname);
			expect(value).to.eq("option_2");
			dialog.clear();
			dialog.hide();
		});
	});
});
