context("Assignment Rule", () => {
	before(() => {
		cy.login();
	});

	it("Custom grid buttons work", () => {
		cy.new_form("Assignment Rule");
		cy.findByRole("button", { name: "All Days" }).should("be.visible").click();
		cy.wait(2000);
		cy.window()
			.its("cur_frm")
			.then((frm) => {
				expect(frm.doc.assignment_days.length).to.equal(7);
			});
	});
});
