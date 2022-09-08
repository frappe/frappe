context("Grid Keyboard Shortcut", () => {
	let total_count = 0;
	before(() => {
		cy.login();
	});
	beforeEach(() => {
		cy.reload();
		cy.visit("/app/contact/new-contact-1");
		cy.get('.frappe-control[data-fieldname="email_ids"]').find(".grid-add-row").click();
	});
	it("Insert new row at the end", () => {
		cy.add_new_row_in_grid(
			"{ctrl}{shift}{downarrow}",
			(cy, total_count) => {
				cy.get('[data-name="new-contact-email-1"]').should(
					"have.attr",
					"data-idx",
					`${total_count + 1}`
				);
			},
			total_count
		);
	});
	it("Insert new row at the top", () => {
		cy.add_new_row_in_grid("{ctrl}{shift}{uparrow}", (cy) => {
			cy.get('[data-name="new-contact-email-1"]').should("have.attr", "data-idx", "2");
		});
	});
	it("Insert new row below", () => {
		cy.add_new_row_in_grid("{ctrl}{downarrow}", (cy) => {
			cy.get('[data-name="new-contact-email-1"]').should("have.attr", "data-idx", "1");
		});
	});
	it("Insert new row above", () => {
		cy.add_new_row_in_grid("{ctrl}{uparrow}", (cy) => {
			cy.get('[data-name="new-contact-email-1"]').should("have.attr", "data-idx", "2");
		});
	});
});

Cypress.Commands.add("add_new_row_in_grid", (shortcut_keys, callbackFn, total_count) => {
	cy.get('.frappe-control[data-fieldname="email_ids"]').as("table");
	cy.get("@table").find('.grid-body [data-fieldname="email_id"]').first().click();
	cy.get("@table").find('.grid-body [data-fieldname="email_id"]').first().type(shortcut_keys);

	callbackFn(cy, total_count);
});
