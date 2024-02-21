context("Blog Post", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
	});

	it("Blog Category dropdown works as expected", () => {
		cy.create_records([
			{
				doctype: "Blog Category",
				title: "Category 1",
				published: 1,
			},
			{
				doctype: "Blogger",
				short_name: "John",
				full_name: "John Doe",
			},
			{
				doctype: "Blog Post",
				title: "Test Blog Post",
				content: "Test Blog Post Content",
				blog_category: "category-1",
				blogger: "John",
				published: 1,
			},
		]);
		cy.set_value("Blog Settings", "Blog Settings", { browse_by_category: 1 });
		cy.visit("/blog");
		cy.findByLabelText("Browse by category").select("Category 1");
		cy.location("pathname").should("eq", "/blog/category-1");
		cy.set_value("Blog Settings", "Blog Settings", { browse_by_category: 0 });
		cy.visit("/blog");
		cy.findByLabelText("Browse by category").should("not.exist");
	});
});
