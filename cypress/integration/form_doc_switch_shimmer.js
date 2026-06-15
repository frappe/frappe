describe("Form doc-switch shimmer", { scrollBehavior: false }, () => {
	before(() => {
		cy.login();
		cy.visit("/desk");
	});

	it("adds form-doc-switching class on switch_doc and removes it after refresh_fields", () => {
		// Use ToDo — lightweight, always available, no mandatory fields.
		cy.visit("/desk/todo");
		cy.get(".list-row").should("have.length.gte", 2);

		// Open the first ToDo
		cy.get(".list-row").first().find(".list-subject a").click();
		cy.get("body").should("have.attr", "data-ajax-state", "complete");
		cy.get(".form-doc-switching").should("not.exist");

		// Intercept the next document fetch so we can assert mid-flight
		cy.intercept("GET", "/api/resource/ToDo/**").as("fetchDoc");

		// Go back to list and open the second ToDo
		cy.go("back");
		cy.get(".list-row").eq(1).find(".list-subject a").click();

		// Class should be present while the doc is loading
		cy.get(".page-container.selected .frappe-control")
			.parents(".page-container")
			.should("have.class", "form-doc-switching");

		// Wait for the fetch to complete
		cy.wait("@fetchDoc");

		// Class must be gone once render_form finishes
		cy.get("body").should("have.attr", "data-ajax-state", "complete");
		cy.get(".form-doc-switching").should("not.exist");
	});

	it("removes form-doc-switching class even when doc has no read permission", () => {
		// Open a ToDo so setup_done = true, then simulate a doc-switch to a doc
		// the user cannot read. We stub has_read_permission after setup so the
		// early-return cleanup path in refresh() is actually exercised.
		cy.visit("/desk/todo");
		cy.get(".list-row").should("have.length.gte", 2);
		cy.get(".list-row").first().find(".list-subject a").click();
		cy.get("body").should("have.attr", "data-ajax-state", "complete");

		cy.window().then((win) => {
			const frm = win.cur_frm;
			const origFetch = frm.fetch_permissions.bind(frm);
			const origHas = frm.has_read_permission.bind(frm);

			// Stub so the next refresh() hits the permission-denied early return
			frm.fetch_permissions = () => {};
			frm.has_read_permission = () => false;

			// switch_doc runs (setup_done=true → class added), then early return removes it
			frm.refresh("fake-restricted-doc");

			frm.fetch_permissions = origFetch;
			frm.has_read_permission = origHas;
		});

		cy.get(".form-doc-switching").should("not.exist");
	});
});

describe("Form doc-switch shimmer — CSS", { scrollBehavior: false }, () => {
	before(() => {
		cy.login();
		cy.visit("/desk");
	});

	it("control-input-wrapper has shimmer pseudo-element styles while switching", () => {
		cy.visit("/desk/todo");
		cy.get(".list-row").should("have.length.gte", 2);

		cy.get(".list-row").first().find(".list-subject a").click();
		cy.get("body").should("have.attr", "data-ajax-state", "complete");

		// Intercept so the fetch is delayed long enough to observe the shimmer
		cy.intercept("GET", "/api/resource/ToDo/**", (req) => {
			req.on("response", (res) => {
				res.setDelay(500); // hold response for 500ms
			});
		}).as("slowFetch");

		cy.go("back");
		cy.get(".list-row").eq(1).find(".list-subject a").click();

		// While the fetch is in flight the wrapper must carry the class
		cy.get(".page-container")
			.should("have.class", "form-doc-switching")
			.find(".control-input-wrapper")
			.should("exist");

		cy.wait("@slowFetch");
		cy.get("body").should("have.attr", "data-ajax-state", "complete");

		// After load the class must be gone
		cy.get(".form-doc-switching").should("not.exist");
	});

	it("field labels remain visible during the switch", () => {
		cy.visit("/desk/todo");
		cy.get(".list-row").should("have.length.gte", 2);
		cy.get(".list-row").first().find(".list-subject a").click();
		cy.get("body").should("have.attr", "data-ajax-state", "complete");

		cy.intercept("GET", "/api/resource/ToDo/**", (req) => {
			req.on("response", (res) => {
				res.setDelay(400);
			});
		}).as("slowFetch2");

		cy.go("back");
		cy.get(".list-row").eq(1).find(".list-subject a").click();

		// Labels (not inside control-input-wrapper) must remain readable
		cy.get(".form-doc-switching .frappe-control label").first().should("be.visible");

		cy.wait("@slowFetch2");
		cy.get("body").should("have.attr", "data-ajax-state", "complete");
	});
});
