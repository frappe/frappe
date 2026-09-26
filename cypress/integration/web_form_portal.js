import web_form_source_doctype from "../fixtures/web_form_source_doctype";
import { seed_web_form } from "../support/web_form";

const ROUTE = "multiselect-note";

function seed_portal_form(roles_df = {}, more_fields = []) {
	return seed_web_form(
		[
			{ fieldname: "title", fieldtype: "Data", label: "Title", reqd: 1 },
			{
				fieldname: "roles",
				fieldtype: "Table MultiSelect",
				label: "Roles",
				options: "Has Role",
				...roles_df,
			},
			...more_fields,
		],
		{
			title: ROUTE,
			route: ROUTE,
			doc_type: web_form_source_doctype.name,
			published: 1,
			login_required: 0,
		}
	);
}

function roles_input() {
	return cy.get('.web-form .frappe-control[data-fieldname="roles"] input');
}

function submit() {
	cy.get(".web-form-actions button").contains("Save").click();
}

// the portal is a guest's page, so log out after seeding and back in to read the result
context("Web Form Table MultiSelect", () => {
	before(() => {
		cy.login();
		cy.visit("/desk");
		cy.insert_doc("DocType", web_form_source_doctype, true);
	});

	beforeEach(() => {
		cy.login();
		cy.visit("/desk");
	});

	it("Guest picks an option shipped with the page and saves it", () => {
		seed_portal_form();
		cy.call("logout");

		// the desk search endpoint is not guest-allowed, so the control must not ask it
		cy.intercept("POST", "/api/method/frappe.desk.search.search_link").as("search");

		cy.visit(`/${ROUTE}/new`);
		cy.fill_field("title", "Multiselect Guest Note");
		roles_input().type("System Man");
		cy.contains('[role="option"]:visible', "System Manager").click();
		cy.get(".web-form .tb-selected-value .btn-link-to-form").should(
			"have.text",
			"System Manager"
		);

		// the list stays open after a pick and covers Save
		roles_input().type("{esc}");
		submit();
		cy.get(".success-page").should("be.visible");
		cy.get("@search.all").should("have.length", 0);

		cy.login();
		cy.call("frappe.client.get_value", {
			doctype: web_form_source_doctype.name,
			filters: { title: "Multiselect Guest Note" },
			fieldname: "name",
		}).then((r) => {
			cy.call("frappe.client.get", {
				doctype: web_form_source_doctype.name,
				name: r.message.name,
			}).then((doc) => {
				expect(doc.message.roles.map((row) => row.role)).to.deep.eq(["System Manager"]);
			});
		});
	});

	it("Next stops on a page that leaves a required Table MultiSelect empty", () => {
		seed_portal_form({ reqd: 1 }, [
			{ fieldtype: "Page Break", label: "More" },
			{ fieldname: "kind", fieldtype: "Select", label: "Kind" },
		]);
		cy.call("logout");

		cy.visit(`/${ROUTE}/new`);
		cy.fill_field("title", "Multiselect Empty Note");
		cy.get(".btn-next").click();

		// the pill box carries .form-control, so the check has to find the input instead
		cy.get(".msgprint")
			.should("contain.text", "Mandatory fields required")
			.and("contain.text", "Roles");
		cy.get(".btn-next").should("be.visible");
	});
});

context("Web Form Table", () => {
	const GRID_ROUTE = "grid-slideshow";

	beforeEach(() => {
		cy.login();
		cy.visit("/desk");
		// a child table with no Check column, since the portal grid posts a Check as "0"
		seed_web_form(
			[
				{ fieldname: "slideshow_name", fieldtype: "Data", label: "Name", reqd: 1 },
				{
					fieldname: "slideshow_items",
					fieldtype: "Table",
					label: "Slides",
					options: "Website Slideshow Item",
				},
			],
			{
				title: GRID_ROUTE,
				route: GRID_ROUTE,
				doc_type: "Website Slideshow",
				published: 1,
				login_required: 0,
			}
		);
		cy.call("logout");
	});

	it("Deletes a row from its row form and saves the rest", () => {
		const name = `Grid Delete ${Date.now()}`;
		cy.visit(`/${GRID_ROUTE}/new`);
		cy.fill_field("slideshow_name", name);

		cy.get('.web-form [data-fieldname="slideshow_items"]').as("table");
		["One", "Two", "Three"].forEach((heading, i) => {
			const cell = `.grid-row[data-idx="${i + 1}"] [data-fieldname="heading"]`;
			cy.get("@table").find(".grid-add-row").click();
			cy.get("@table").find(cell).click();
			cy.get("@table").find(`${cell} input`).type(heading);
		});

		cy.get("@table").find('.grid-row[data-idx="2"] .btn-open-row').click();
		cy.get("@table").find(".grid-row-open .grid-delete-row").click();

		// the grid renders a copy of df.get_data(), so the delete has to reach that copy.
		// The save below proves which row went, this proves the grid saw it go
		cy.get("@table").find(".grid-body .grid-row").should("have.length", 2);

		submit();
		cy.get(".success-page").should("be.visible");

		cy.login();
		cy.call("frappe.client.get", { doctype: "Website Slideshow", name }).then((doc) => {
			expect(doc.message.slideshow_items.map((row) => row.heading)).to.deep.eq([
				"One",
				"Three",
			]);
		});
	});
});
