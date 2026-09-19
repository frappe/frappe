context("Dialog helpers", () => {
	before(() => {
		cy.login();
		cy.visit("/desk");
	});

	function close_and_check_removed(open_dialog, message) {
		cy.window().its("frappe").then(open_dialog).as("dialog");
		cy.get("@dialog").its("display").should("be.true");
		cy.contains(".modal:visible", message).find(".btn-modal-close").click();
		cy.contains(message).should("not.exist");
	}

	it("removes the frappe.confirm dialog from the DOM once hidden", () => {
		close_and_check_removed(
			(frappe) => frappe.confirm("Archive the Q3 sales report?"),
			"Archive the Q3 sales report?"
		);
	});

	it("removes the frappe.warn dialog from the DOM once hidden", () => {
		close_and_check_removed(
			(frappe) => frappe.warn("Cancel Invoice", "Cancelling this invoice cannot be undone."),
			"Cancelling this invoice cannot be undone."
		);
	});

	it("removes the frappe.prompt dialog from the DOM once hidden", () => {
		close_and_check_removed(
			(frappe) => frappe.prompt("Rename Project", () => {}, "Rename Project"),
			"Rename Project"
		);
	});

	it("removes the frappe.show_progress dialog from the DOM once hidden", () => {
		cy.window()
			.its("frappe")
			.then((frappe) => frappe.show_progress("Importing Customers", 40, 100))
			.as("dialog");
		cy.get("@dialog").its("display").should("be.true");
		cy.window()
			.its("frappe")
			.then((frappe) => frappe.hide_progress());
		cy.contains("Importing Customers").should("not.exist");
	});
});
