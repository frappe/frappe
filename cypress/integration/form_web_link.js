context("Form Web Link", () => {
	const route = "cypress-web-link-page";

	const set_form_sidebar = (value) => {
		cy.window()
			.its("frappe")
			.then((frappe) => {
				cy.set_value("User", frappe.session.user, { form_sidebar: value });
			});
	};

	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.remove_doc("Web Page", route, true);
		cy.insert_doc("Web Page", {
			title: "Cypress Web Link Page",
			route: route,
			published: 1,
			content_type: "HTML",
			main_section_html: "<p>Cypress</p>",
		});
		set_form_sidebar(0);
	});

	after(() => {
		cy.login();
		cy.visit("/desk/website");
		set_form_sidebar(1);
		cy.remove_doc("Web Page", route, true);
	});

	it("renders a published website page when the form sidebar is disabled", () => {
		cy.login();
		cy.visit(`/desk/web-page/${route}`);

		cy.get('.frappe-control[data-fieldname="title"]').should("be.visible");
		cy.get('.frappe-control[data-fieldname="route"]').should("be.visible");
	});
});
