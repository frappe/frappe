context("Timeline Realtime Updates", () => {
	const doctype = "Test Autoincrement Comment";
	const route = "test-autoincrement-comment";
	// `.timeline-items` also matches the action bar above the feed
	const timeline = ".form-footer .timeline-items:not(.timeline-actions)";

	before(() => {
		cy.login();
		cy.visit("/desk/doctype");
		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				// `create_doctype` names its doctypes with `autoincrement`, so the
				// documents get integer names.
				return frappe.xcall("frappe.tests.ui_test_helpers.create_doctype", {
					name: doctype,
					fields: [
						{
							label: "Title",
							fieldname: "title",
							fieldtype: "Data",
							in_list_view: 1,
						},
					],
				});
			});
	});

	beforeEach(() => {
		// also runs on a retry, so the test never inherits a half-finished page
		cy.login();
		cy.visit("/desk");
	});

	it("shows a comment on an integer-named document without a reload", () => {
		cy.insert_doc(doctype, { title: "Realtime comment target" }).then((doc) => {
			// The whole point of this test: the document name is a number here, while
			// the route the form is opened with only ever carries its string form.
			expect(doc.name).to.be.a("number");

			cy.visit(`/desk/${route}/${doc.name}`);
			cy.get(timeline).should("exist");
			cy.window()
				.its("frappe.realtime")
				.should((realtime) => {
					expect(realtime.socket.connected).to.be.true;
					expect(realtime.open_docs).to.include(`${doctype}:${doc.name}`);
				});
			// Joining the doc room costs the server an async permission check, and the
			// event only reaches sockets already in the room.
			cy.wait(1000);

			const content = `Realtime comment ${Date.now()}`;

			cy.window()
				.its("frappe")
				.then((frappe) => {
					// Added over HTTP, so `docinfo_update` over the socket is the only
					// thing that can put this comment in the open form's timeline. The
					// server sends `reference_name` as an integer (the link validator
					// rewrites it with the name read back from the database), which the
					// listener has to match against the form's string `docname`.
					return frappe.xcall("frappe.desk.form.utils.add_comment", {
						reference_doctype: doctype,
						reference_name: String(doc.name),
						content: content,
						comment_email: "Administrator",
						comment_by: "Administrator",
					});
				});

			cy.get(timeline, { timeout: 30000 }).should("contain.text", content);
			cy.get(".form-footer .comment-count").should("contain.text", "(1)");
		});
	});
});
