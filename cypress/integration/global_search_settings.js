context("Global Search Settings — configure search fields", () => {
	const GS_GRID = '.frappe-control[data-fieldname="allowed_in_global_search"]';

	/** Editable-grid Link fields only mount after the row is active (toggle_editable_row → make_control). */
	function ensure_first_priority_row() {
		cy.get(`${GS_GRID} .grid-body`).then(($body) => {
			if ($body.find(".grid-row").length === 0) {
				cy.get(`${GS_GRID} .grid-add-row`).click();
			}
		});
		cy.get(`${GS_GRID} .grid-body .grid-row[data-idx="1"]`).should("exist");
	}

	function activate_document_type_cell(rowAlias = "@row") {
		cy.get(rowAlias).find('[data-fieldname="document_type"]').click();
		cy.get(rowAlias).find('[data-fieldname="document_type"] input').should("exist");
	}

	/** Awesomplete dropdown is attached via `aria-owns` (often outside the row); items are `div[role="option"]`, not `li`. */
	function select_document_type_link(rowAlias, label) {
		cy.get(rowAlias).find('[data-fieldname="document_type"] input').as("docTypeInput");
		cy.get("@docTypeInput").clear().focus().type(label, { delay: 100 });
		cy.get("@docTypeInput").invoke("attr", "aria-owns").should("match", /\w+/);
		cy.get("@docTypeInput")
			.invoke("attr", "aria-owns")
			.then((ownsId) => {
				const sel = `#${CSS.escape(ownsId)}`;
				cy.get(sel).should("be.visible");
				cy.get(sel)
					.find('[role="option"]')
					.filter((_, el) => {
						const $el = Cypress.$(el);
						const primary =
							$el.find("strong").first().text().trim() ||
							$el.text().trim().split("\n")[0];
						return primary === label;
					})
					.should("have.length", 1)
					.scrollIntoView()
					.click({ force: true });
			});
		cy.get("@docTypeInput").blur();
		cy.get("@docTypeInput").should("have.value", label);
	}

	beforeEach(() => {
		cy.login("Administrator", Cypress.env("adminPassword") || "admin");
		cy.visit("/desk/global-search-settings");
		cy.get("body").should("have.attr", "data-ajax-state", "complete");
		cy.get(`${GS_GRID}`).should("exist");
	});

	it("shows a message when Configure is clicked without Document Type", () => {
		cy.get('.frappe-control[data-fieldname="allowed_in_global_search"]')
			.find(".grid-add-row")
			.click();
		cy.get(
			'.frappe-control[data-fieldname="allowed_in_global_search"] .grid-body .grid-row:last'
		)
			.find('[data-fieldname="configure"] button')
			.click();
		cy.get(".msgprint").should("contain", "Please select Document Type first");
	});

	it("opens configure dialog with MultiCheck field options and filter search", () => {
		ensure_first_priority_row();
		cy.get(`${GS_GRID} .grid-body .grid-row[data-idx="1"]`).as("row");
		activate_document_type_cell();
		select_document_type_link("@row", "ToDo");

		cy.get("@row").find('[data-fieldname="configure"] button').click();

		cy.get_open_dialog().find(".modal-title").should("contain", "Configure search fields");
		cy.get_open_dialog().should("contain", "ToDo");
		cy.get_open_dialog()
			.find('.checkbox-options input[type="checkbox"][data-unit="name"]')
			.should("exist");

		const unlikely = "xyz-nonmatching-global-search-filter-12345";
		cy.get_open_dialog().find('[data-element="search"]').clear().type(unlikely);
		cy.get_open_dialog()
			.find(".checkbox-options .unit-checkbox:visible")
			.should("have.length", 0);
		cy.get_open_dialog().find('[data-element="search"]').clear();
		cy.get_open_dialog()
			.find(".checkbox-options .unit-checkbox:visible")
			.should((els) => {
				expect(els.length).to.be.greaterThan(0);
			});

		cy.get_open_dialog().find(".btn-modal-close").click();
		cy.get(".modal:visible").should("not.exist");
	});

	it("saves selected fields and shows success toast", () => {
		cy.intercept(
			"POST",
			"/api/method/frappe.desk.doctype.global_search_settings.global_search_settings.update_global_search_fields"
		).as("update_global_search_fields");

		ensure_first_priority_row();
		cy.get(`${GS_GRID} .grid-body .grid-row[data-idx="1"]`).as("row");
		activate_document_type_cell();
		// Must not be a Core module DocType — API rejects those (no toast; server error).
		select_document_type_link("@row", "ToDo");

		cy.get("@row").find('[data-fieldname="configure"] button').click();

		cy.get_open_dialog()
			.find('.checkbox-options input[type="checkbox"][data-unit="name"]')
			.should("exist");

		cy.get_open_dialog()
			.find(".modal-footer .standard-actions .btn-primary")
			.contains("Save")
			.click({ force: true });

		cy.wait("@update_global_search_fields").then(({ response }) => {
			expect(response.statusCode).to.eq(200);
			expect(response.body.exc, JSON.stringify(response.body)).to.be.undefined;
			expect(response.body.message?.success).to.eq(true);
		});

		cy.get('[role="alert"].desk-alert .alert-message', { timeout: 25000 }).should(
			"contain",
			"Search fields updated."
		);
	});
});
