context("Mention", () => {
	const test_user = "mention_test_user@example.com";

	before(() => {
		cy.visit("/");
		cy.login();
		cy.visit("/desk/website");

		// create a test user to mention from
		cy.insert_doc(
			"User",
			{
				email: test_user,
				first_name: "Mention",
				last_name: "Tester",
				send_welcome_email: 0,
				roles: [{ role: "System Manager" }],
			},
			true
		);
	});

	it("renders the Mention blot when mentioning Administrator in a comment", () => {
		// create a saved document so the comment box (form footer) is available
		cy.insert_doc(
			"ToDo",
			{
				description: "Mention blot test",
			},
			true
		).then((todo) => {
			cy.visit(`/desk/todo/${todo.name}`);
		});

		cy.get("body").should("have.attr", "data-ajax-state", "complete");

		// open the comment box and trigger a mention
		cy.get(".comment-input-wrapper .ql-editor").click().type("@Admin");

		// the mention dropdown should surface Administrator
		cy.get(".ql-mention-list-container .ql-mention-list-item")
			.contains("Administrator")
			.click();

		// the Mention blot should render with the denotation char and value
		cy.get(".comment-input-wrapper .ql-editor .mention")
			.should("have.attr", "data-value", "Administrator")
			.and("have.attr", "data-denotation-char", "@");

		cy.get(".comment-input-wrapper .ql-editor .mention").should(($mention) => {
			expect($mention.find(".ql-mention-denotation-char").text()).to.eq("@");
			expect($mention.text().trim()).to.eq("@Administrator");
		});
	});

	after(() => {
		cy.visit("/desk/website");
		cy.wait(1000);
		cy.remove_doc("User", test_user, true); // true = ignore_missing
	});
});
