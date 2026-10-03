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

	// Link search results for doctypes without `show_title_field_in_link` carry no label,
	// so they end up with label "" and used to match an empty input on blur.
	it("should not add an unlabelled item when an empty field loses focus", () => {
		const fieldname = "multiselect_1";
		cy.dialog({
			title: "Multiselect",
			fields: [
				{
					label: "Assign To",
					fieldname: fieldname,
					fieldtype: "MultiSelectPills",
					get_data: () => [
						{ value: "a@example.com", description: "A User" },
						{ value: "b@example.com", description: "B User" },
					],
				},
			],
		}).as("dialog");

		cy.get(`input[data-fieldname=${fieldname}]`).as("input");
		cy.wait(500);
		cy.get("@input").focus();
		cy.get(".awesomplete ul li").should("have.length", 2);
		cy.get(".modal-title:visible").click();
		cy.get("@dialog").then((dialog) => {
			expect(dialog.get_value(fieldname)).to.have.length(0);
		});
		cy.get(".tb-selected-value").should("not.exist");

		// selecting from the dropdown still works
		cy.get("@input").focus();
		cy.get(".awesomplete ul li").first().click();
		cy.get("@dialog").then((dialog) => {
			expect(dialog.get_value(fieldname)).to.deep.eq(["a@example.com"]);
			dialog.clear();
			dialog.hide();
		});
	});
});
