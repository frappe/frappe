context("Control Markdown Editor", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
	});

	it("should allow inserting images by drag and drop", () => {
		cy.visit("/app/web-page/new");
		cy.fill_field("content_type", "Markdown", "Select");
		cy.get_field("main_section_md", "Markdown Editor").attachFile("sample_image.jpg", {
			subjectType: "drag-n-drop",
		});
		cy.click_modal_primary_button("Upload");
		cy.get_field("main_section_md", "Markdown Editor").should(
			"contain",
			"![](/private/files/sample_image"
		);
	});
});
