import custom_link_title_doctype from "../fixtures/custom_link_title_doctype";
const doctype_name = custom_link_title_doctype.name;

context("Report View Link Titles", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.insert_doc("DocType", custom_link_title_doctype, true);
		cy.clear_cache();
		cy.insert_doc(
			doctype_name,
			{
				title: "Renewal Reminder",
				display_name: "Renewal reminder for Contoso",
			},
			true
		);
		cy.insert_doc(
			doctype_name,
			{
				title: "Contract Follow Up",
				display_name: "Contract follow up",
				parent_entry: "Renewal Reminder",
			},
			true
		);
	});

	it("skips the link title lookup for a blank Link column", () => {
		const requested_docnames = [];
		cy.intercept("POST", "/api/method/frappe.desk.search.get_link_title", (req) => {
			requested_docnames.push(req.body.docname);
		}).as("link_title");

		cy.visit(`/desk/List/${doctype_name}/Report`);

		cy.wait("@link_title").then(() => {
			expect(requested_docnames).to.not.include("null");
			expect(requested_docnames).to.include("Renewal Reminder");
		});
	});
});
