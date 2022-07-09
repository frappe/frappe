const list_view = "/app/todo";

// test round trip with filter types

const test_queries = [
	"?status=Open",
	`?date=%5B"Between"%2C%5B"2022-06-01"%2C"2022-06-30"%5D%5D`,
	`?date=%5B">"%2C"2022-06-01"%5D`,
	`?name=%5B"like"%2C"%2542%25"%5D`,
	`?status=%5B"not%20in"%2C%5B"Open"%2C"Closed"%5D%5D`,
];

describe("SPA Routing", { scrollBehavior: false }, () => {
	before(() => {
		cy.login();
		cy.go_to_list("ToDo");
	});

	after(() => {
		cy.clear_filters(); // avoid flake in future tests
	});

	it("should apply filter on list view from route", () => {
		test_queries.forEach((query) => {
			const full_url = `${list_view}${query}`;
			cy.visit(full_url);
			cy.findByTitle("To Do").should("exist");

			const expected = new URLSearchParams(query);
			cy.location().then((loc) => {
				const actual = new URLSearchParams(loc.search);
				// This might appear like a dumb test checking visited URL to itself
				// but it's actually doing a round trip
				// URL with params -> parsed filters -> new URL
				// if it's same that means everything worked in between.
				expect(actual.toString()).to.eq(expected.toString());
			});
		});
	});
});
