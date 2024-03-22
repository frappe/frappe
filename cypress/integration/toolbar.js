context("Toolbar", () => {
	before(() => {
		cy.login();
	});
	it("Checks the functionality for announcements added through Navbar Settings", () => {
		// Navigate to the Navbar Settings DocType
		cy.visit("/app/navbar-settings/");

		// Set an initial value for the announcement
		cy.fill_field("announcement_widget", "Site Maintenance: 3-4 PM", "Text Editor")
			.as("announcement_widget")
			.wait(300)
			.save();

		// Check if the announcement widget appears
		cy.reload();
		cy.get(".announcement-widget").should("be.visible");
		cy.get(".announcement-widget div.container").should("contain", "Site Maintenance: 3-4 PM");

		// Click on the close button to dismiss the announcement
		cy.get(".announcement-widget div.close-message").click();

		// Check if the widget is permanently dismissed
		cy.reload();
		cy.get(".announcement-widget").should("not.exist");

		// Set a new announcement from Navbar Settings
		cy.get("@announcement_widget").clear({ force: true });
		cy.fill_field("announcement_widget", "Site Maintenance: 4-5 PM", "Text Editor")
			.wait(300)
			.save();

		// Check if the new announcement appears
		cy.reload();
		cy.get(".announcement-widget").should("be.visible");
		cy.get(".announcement-widget div.container").should("contain", "Site Maintenance: 4-5 PM");

		cy.get("@announcement_widget").clear({ force: true }).wait(300).save();
	});
});
