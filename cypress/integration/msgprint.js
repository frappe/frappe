context("Msgprint", () => {
	before(() => {
		cy.login();
		cy.visit("/app/todo");
	});

	it("keeps an open message when the response carries only toasts", () => {
		cy.window().then((win) => {
			win.frappe.msgprint({ message: "client message", title: "client title" });
			win.frappe.request.cleanup(
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
		cy.hide_dialog();
	});

	it("clears an open message before showing a server message", () => {
		cy.window().then((win) => {
			win.frappe.msgprint({ message: "client message", title: "client title" });
			win.frappe.request.cleanup(
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
		cy.hide_dialog();
	});
});
