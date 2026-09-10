context("Email Composer", () => {
	const test_user = "test_email_composer@example.com";

	before(() => {
		cy.login();
		cy.visit("/desk/user");
		cy.insert_doc(
			"User",
			{
				email: test_user,
				first_name: "Test Email Composer",
				language: "de",
				send_welcome_email: 0,
			},
			true
		);
	});

	it("picks print language from the document, not the system language", () => {
		cy.visit(`/desk/user/${test_user}`);
		cy.window().its("cur_frm.doc.language").should("eq", "de");

		cy.window().then((win) => {
			new win.frappe.views.CommunicationComposer({ frm: win.cur_frm, doc: win.cur_frm.doc });
		});

		cy.get_open_dialog().should("be.visible");
		cy.window().its("cur_dialog").invoke("get_value", "print_language").should("eq", "de");
	});
});
