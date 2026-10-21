context("Control MultiSelect", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
	});

	it("does not suggest a value that is already selected", () => {
		cy.dialog({
			title: "MultiSelect",
			fields: [
				{
					label: "Select options",
					fieldname: "multiselect",
					fieldtype: "MultiSelect",
					options: ["Option 1", "Option 2", "Option 3"],
				},
			],
		});
		cy.get(".control-input > .awesomplete > input[data-fieldname=multiselect]").as("input");
		cy.get("@input").type("2", { delay: 100 });
		cy.get("@input").parent().find("li").should("contain", "Option 2");
		cy.get("@input").type("{enter}Option", { delay: 100 });

		cy.get("@input")
			.parent()
			.find("li")
			.should(($li) => {
				const suggestions = [...$li].map((li) => li.textContent.trim());
				expect(suggestions).to.deep.equal(["Option 1", "Option 3"]);
			});
	});
});
