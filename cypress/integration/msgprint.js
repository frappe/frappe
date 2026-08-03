context("Msgprint", () => {
	before(() => {
		cy.login();
	});

	beforeEach(() => {
		cy.visit("/app/todo");
	});

	it("keeps an open message when the response carries only toasts", () => {
		cy.window()
			.its("frappe")
			.then((frappe) => {
				frappe.msgprint({ message: "client message", title: "client title" });
				frappe.request.cleanup(
					{},
					{
						_server_messages: JSON.stringify([
							JSON.stringify({ message: "Saved", alert: 1 }),
						]),
					}
				);
			});
		cy.get(".msgprint-dialog").should("be.visible");
		cy.get(".msgprint").should("contain", "client message");
	});

	it("clears an open message before showing a server message", () => {
		cy.window()
			.its("frappe")
			.then((frappe) => {
				frappe.msgprint({ message: "client message", title: "client title" });
				frappe.request.cleanup(
					{},
					{
						_server_messages: JSON.stringify([
							JSON.stringify({ message: "server message" }),
						]),
					}
				);
			});
		cy.get(".msgprint")
			.should("contain", "server message")
			.should("not.contain", "client message");
	});
});
