// Create-flow coverage for the Print Format Builder (the page renamed
// from "print-format-builder-beta" → "print-format-builder" in this PR).
//
// Each test generates its own unique PF_NAME and tears it down in
// afterEach, so Cypress retries don't collide with leftover docs.

context("Print Format Builder — create flow", () => {
	let PF_NAME;

	before(() => {
		cy.login();
		cy.visit("/app");
	});

	beforeEach(() => {
		PF_NAME = `Cypress PF ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
	});

	afterEach(() => {
		// best-effort cleanup — DELETE swallows 404 / 417 via failOnStatusCode.
		// Use .then() with optional-chaining so we never block on csrf_token
		// being absent (e.g. when the test failed before visiting a frappe page).
		cy.window().then((win) => {
			const csrf_token = win.frappe?.csrf_token;
			if (!csrf_token) return;
			cy.request({
				method: "DELETE",
				url: `/api/resource/Print Format/${encodeURIComponent(PF_NAME)}`,
				headers: { "X-Frappe-CSRF-Token": csrf_token },
				failOnStatusCode: false,
			});
		});
	});

	// 1. Page loads with the Create-or-Edit dialog
	it("shows the Create or Edit Print Format dialog", () => {
		cy.visit("/app/print-format-builder");
		cy.get_open_dialog().should("contain", "Create or Edit Print Format");
		cy.get_open_dialog().find(".btn-primary").should("contain", "Create");
	});

	// 2. Filling the dialog and clicking Create inserts a beta format
	it("creates a new Print Format with print_format_builder_beta=1", () => {
		cy.intercept("POST", "api/method/frappe.client.insert").as("insert");

		cy.visit("/app/print-format-builder");
		cy.get_open_dialog().should("be.visible");

		// The print_format_name field has depends_on: action === 'Create' and
		// the dialog runs set_value('action', 'Create') *after* show(), so
		// the depends_on reveal races with the first keystroke and
		// cy.fill_field drops the leading 'C'. Set the value via .invoke('val')
		// and trigger input/change so Frappe's Control picks it up without
		// going through the keyboard simulator at all.
		cy.fill_field("doctype", "ToDo", "Link");
		cy.get_open_dialog()
			.find('[data-fieldname="print_format_name"] input:visible')
			.should("be.enabled")
			.invoke("val", PF_NAME)
			.trigger("input")
			.trigger("change");

		cy.get_open_dialog().find(".btn-primary").contains("Create").click();

		// frappe.client.insert returns the inserted doc — inspect it directly
		// rather than round-tripping through frappe.db.get_value (which can
		// strip fields the user can't read in list view).
		cy.wait("@insert").then((interception) => {
			expect(interception.response.statusCode).to.equal(200);
			const doc = interception.response.body.message;
			expect(doc.name).to.equal(PF_NAME);
			expect(doc.doc_type).to.equal("ToDo");
			expect(Number(doc.print_format_builder_beta)).to.equal(1);
		});
	});

	// 3. Loading the builder for an existing format and saving a change
	//    (creates the doc via API up-front so this test doesn't depend on #2)
	it("loads the builder and Save persists a margin change", () => {
		// Navigate to a stable frappe page so frappe.csrf_token is available
		// before cy.insert_doc tries to read it. Without this, the previous
		// test's SPA navigation may leave the window in a mid-transition state.
		cy.visit("/app");

		// Pre-populate format_data so PrintFormatBuilder.vue's onMounted
		// auto-save doesn't fire on first load (that auto-save's follow-up
		// fetch would otherwise overwrite our typed value before we click Save).
		cy.insert_doc(
			"Print Format",
			{
				name: PF_NAME,
				doc_type: "ToDo",
				print_format_builder_beta: 1,
				format_data: JSON.stringify({ header: "", sections: [] }),
			},
			true
		);

		cy.intercept("POST", "api/method/frappe.client.save").as("save");
		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		// Open the Format tab in the sidebar (contains page margin inputs).
		// Wait for the tab bar to confirm the builder has fully rendered.
		cy.get(".pfb-tab[title='Format']", { timeout: 30000 }).click();
		cy.get(".pfb-margin-grid").should("be.visible");

		// Make sure no auto-save / freeze overlay is still in flight before we type.
		cy.get(".freeze").should("not.exist");
		cy.get(".indicator-pill.orange").should("not.exist");

		// Change Top margin to 9. Explicit change trigger because the Vue
		// input uses `@change` on a one-way `:value` binding and Cypress's
		// .blur() alone doesn't always emit a synthetic change event that
		// the Vue listener picks up.
		cy.contains(".pfb-margin-cell label", "Top")
			.closest(".pfb-margin-cell")
			.find('input[type="number"]')
			.clear()
			.type("9")
			.trigger("change")
			.blur();

		// dirty pill appears
		cy.get(".indicator-pill.orange", { timeout: 5000 }).should("contain", "Not Saved");

		// Save via the page's primary action; assert the saved doc reflects
		// the new margin (frappe.client.save returns the persisted doc).
		cy.contains(".page-actions .primary-action", "Save").click({ force: true });
		cy.wait("@save").then((interception) => {
			expect(interception.response.statusCode).to.equal(200);
			expect(Number(interception.response.body.message.margin_top)).to.equal(9);
		});
		cy.get(".indicator-pill.orange").should("not.exist");
	});

	// 4. Outline tab: clicking a section scrolls to it and selects it
	it("outline tab selects a section on click", () => {
		cy.visit("/app");

		cy.insert_doc(
			"Print Format",
			{
				name: PF_NAME,
				doc_type: "ToDo",
				print_format_builder_beta: 1,
				format_data: JSON.stringify({
					sections: [
						{ label: "Alpha", columns: [{ label: "", fields: [] }] },
						{ label: "Beta", columns: [{ label: "", fields: [] }] },
					],
					header: { columns: [{ label: "", fields: [] }] },
					footer: { columns: [{ label: "", fields: [] }] },
				}),
			},
			true
		);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		// Switch to Outline tab
		cy.get(".pfb-tab[title='Outline']", { timeout: 30000 }).click();
		cy.contains(".pfb-outline-item", "Beta").click();

		// Inspector should switch to Section and show "Beta"
		cy.get(".pfb-inspector").should("contain", "Section");
		cy.get(".pfb-inspector").should("contain", "Beta");

		// The clicked outline item should be active
		cy.contains(".pfb-outline-item", "Beta").should("have.class", "active");
	});

	// 5. Field inspector breadcrumb navigates back to parent section
	it("field breadcrumb navigates to parent section", () => {
		cy.visit("/app");

		cy.insert_doc(
			"Print Format",
			{
				name: PF_NAME,
				doc_type: "ToDo",
				print_format_builder_beta: 1,
				format_data: JSON.stringify({
					sections: [
						{
							label: "Details",
							columns: [
								{
									label: "",
									fields: [
										{
											fieldtype: "Data",
											fieldname: "description",
											label: "Description",
										},
									],
								},
							],
						},
					],
					header: { columns: [{ label: "", fields: [] }] },
					footer: { columns: [{ label: "", fields: [] }] },
				}),
			},
			true
		);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		// Click the Description field to select it
		cy.get(".pfb-tab[title='Outline']", { timeout: 30000 }).click();
		cy.contains(".pfb-outline-item", "Details").click();

		// Now select the field via the canvas
		cy.get(".print-format-container").click();
		cy.contains("[data-pfb-section]", "Details").find(".field").first().click({ force: true });

		// Breadcrumb should appear pointing to "Details"
		cy.get(".pfb-breadcrumb").should("be.visible");
		cy.get(".pfb-breadcrumb-name").should("contain", "Details");

		// Clicking breadcrumb selects the parent section
		cy.get(".pfb-breadcrumb-btn").click();
		cy.get(".pfb-inspector").should("contain", "Section");
		cy.get(".pfb-inspector").should("contain", "Details");
		cy.get(".pfb-breadcrumb").should("not.exist");
	});

	// 6. Format tab: font size change is reflected in canvas
	it("font size change applies to canvas preview", () => {
		cy.visit("/app");

		cy.insert_doc(
			"Print Format",
			{
				name: PF_NAME,
				doc_type: "ToDo",
				print_format_builder_beta: 1,
				format_data: JSON.stringify({
					sections: [],
					header: { columns: [{ label: "", fields: [] }] },
					footer: { columns: [{ label: "", fields: [] }] },
				}),
			},
			true
		);

		cy.intercept("POST", "api/method/frappe.client.save").as("save");
		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get(".pfb-tab[title='Format']", { timeout: 30000 }).click();
		cy.get(".pfb-margin-grid").should("be.visible");

		// Change font size
		cy.contains("label", "Font Size")
			.closest(".form-group")
			.find("input")
			.clear()
			.type("18")
			.trigger("change")
			.blur();

		// Body wrapper (.pfb-body) should have font-size applied
		cy.get(".pfb-body").should(($el) => {
			const fs = $el.css("font-size");
			// 18pt ≈ 24px
			expect(parseInt(fs, 10)).to.be.greaterThan(20);
		});
	});
});
