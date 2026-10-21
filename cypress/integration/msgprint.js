context("Msgprint", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
	});

	it("keeps the primary action of an earlier message in the same response", () => {
		cy.window()
			.its("frappe")
			.then((frappe) => {
				frappe.request.cleanup(
					{},
					{
						_server_messages: JSON.stringify([
							JSON.stringify({
								message: "Newly created user has no roles enabled.",
								primary_action: { label: "Add Roles" },
							}),
							JSON.stringify({ message: "Welcome email sent" }),
						]),
					}
				);
			});

		cy.get(".msgprint-dialog").contains("button", "Add Roles").should("be.visible");
	});
});
