context("Control MultiSelectPills", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
	});

	it("does not suggest a value that is already selected", () => {
		cy.dialog({
			title: "MultiSelectPills",
			fields: [
				{
					label: "Select options",
					fieldname: "multiselect_pills",
					fieldtype: "MultiSelectPills",
					options: ["Option 1", "Option 2", "Option 3"],
				},
			],
		});
		cy.get(".awesomplete > input[data-fieldname=multiselect_pills]").as("input");
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
