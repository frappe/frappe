// UI tests for Print Format Builder (beta) — setup flow and section insert.
//
// Each test provisions its own uniquely-named Print Format and tears it down
// in afterEach, so Cypress retries and parallel runs never collide.

// ─── helpers ─────────────────────────────────────────────────────────────────

function pf_name() {
	return `Cypress PFB ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

function cleanup(win, name) {
	const csrf_token = win.frappe?.csrf_token;
	if (!csrf_token) return;
	cy.request({
		method: "DELETE",
		url: `/api/resource/Print Format/${encodeURIComponent(name)}`,
		headers: { "X-Frappe-CSRF-Token": csrf_token },
		failOnStatusCode: false,
	});
}

// Layout with one empty section — enough to show the canvas without setup screen
function one_section_layout() {
	return JSON.stringify({
		sections: [{ label: "Alpha", columns: [{ label: "", fields: [] }] }],
		header: { columns: [{ label: "", fields: [] }] },
		footer: { columns: [{ label: "", fields: [] }] },
	});
}

// ─── Setup flow ───────────────────────────────────────────────────────────────

context("Print Format Builder — setup flow", () => {
	let PF_NAME;

	before(() => {
		cy.login();
		cy.visit("/app");
	});

	beforeEach(() => {
		PF_NAME = pf_name();
	});

	afterEach(() => {
		cy.window().then((win) => cleanup(win, PF_NAME));
	});

	// 1. New format with no format_data shows the "How do you want to start?" screen
	it("shows setup screen when no layout is saved", () => {
		cy.insert_doc(
			"Print Format",
			{ name: PF_NAME, doc_type: "ToDo", print_format_builder_beta: 1 },
			true
		);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get(".pfb-setup", { timeout: 20000 }).should("be.visible");
		cy.get(".pfb-setup-title").should("contain", "How do you want to start?");
		cy.get(".pfb-setup-option").should("have.length", 2);
		cy.contains(".pfb-setup-option-label", "Start from default").should("be.visible");
		cy.contains(".pfb-setup-option-label", "Start blank").should("be.visible");
	});

	// 2. Format with saved format_data skips the setup screen entirely
	it("skips setup screen when a layout is already saved", () => {
		cy.insert_doc(
			"Print Format",
			{
				name: PF_NAME,
				doc_type: "ToDo",
				print_format_builder_beta: 1,
				format_data: one_section_layout(),
			},
			true
		);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		// Canvas should appear directly — no setup card
		cy.get(".sections-container", { timeout: 20000 }).should("be.visible");
		cy.get(".pfb-setup").should("not.exist");
	});

	// 3. "Start blank" dismisses the setup screen and creates an empty canvas
	it("Start blank dismisses setup and shows empty canvas", () => {
		cy.insert_doc(
			"Print Format",
			{ name: PF_NAME, doc_type: "ToDo", print_format_builder_beta: 1 },
			true
		);

		cy.intercept("POST", "api/method/frappe.client.save").as("save");
		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get(".pfb-setup", { timeout: 20000 }).should("be.visible");
		cy.contains(".pfb-setup-option-label", "Start blank").click();

		// Setup screen gone; canvas visible with no body sections
		cy.get(".pfb-setup").should("not.exist");
		cy.get(".sections-container").should("be.visible");
		cy.get(".section-with-insert").should("not.exist");

		// Save was triggered automatically
		cy.wait("@save").then((interception) => {
			expect(interception.response.statusCode).to.equal(200);
			const layout = JSON.parse(interception.response.body.message.format_data);
			expect(layout.sections).to.deep.equal([]);
		});
	});

	// 4. "Start from default" dismisses the setup screen and populates sections
	it("Start from default dismisses setup and fills canvas with document fields", () => {
		cy.insert_doc(
			"Print Format",
			{ name: PF_NAME, doc_type: "ToDo", print_format_builder_beta: 1 },
			true
		);

		cy.intercept("POST", "api/method/frappe.client.save").as("save");
		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get(".pfb-setup", { timeout: 20000 }).should("be.visible");
		cy.contains(".pfb-setup-option-label", "Start from default").click();

		// Setup screen gone; at least one section with fields should appear
		cy.get(".pfb-setup").should("not.exist");
		cy.get("[data-pfb-section]", { timeout: 10000 }).should("have.length.greaterThan", 0);

		cy.wait("@save").then((interception) => {
			expect(interception.response.statusCode).to.equal(200);
			const layout = JSON.parse(interception.response.body.message.format_data);
			expect(layout.sections.length).to.be.greaterThan(0);
		});
	});
});

// ─── Section insert (+ Add Section) ──────────────────────────────────────────

context("Print Format Builder — section insert", () => {
	let PF_NAME;

	before(() => {
		cy.login();
		cy.visit("/app");
	});

	beforeEach(() => {
		PF_NAME = pf_name();
	});

	afterEach(() => {
		cy.window().then((win) => cleanup(win, PF_NAME));
	});

	// 5. Section insert element exists in DOM (opacity:0 hidden, not display:none)
	it("section insert element is present in DOM between sections", () => {
		cy.insert_doc(
			"Print Format",
			{
				name: PF_NAME,
				doc_type: "ToDo",
				print_format_builder_beta: 1,
				format_data: one_section_layout(),
			},
			true
		);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);
		cy.get(".sections-container", { timeout: 20000 }).should("be.visible");

		// The insert strip must exist — it's opacity:0 but NOT display:none
		cy.get(".section-insert").should("exist");
		cy.get(".section-insert").first().should("not.have.css", "display", "none");
		cy.get(".section-insert-btn").first().should("contain", "Add Section");
	});

	// 6. Clicking the insert strip before a section adds a new section above it
	it("clicking section insert before a section inserts a new section", () => {
		cy.insert_doc(
			"Print Format",
			{
				name: PF_NAME,
				doc_type: "ToDo",
				print_format_builder_beta: 1,
				format_data: one_section_layout(),
			},
			true
		);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);
		cy.get("[data-pfb-section]", { timeout: 20000 }).should("have.length", 1);

		// The insert strip sits above the section — force:true bypasses opacity:0
		cy.get(".section-with-insert .section-insert").first().click({ force: true });

		cy.get("[data-pfb-section]").should("have.length", 2);
	});

	// 7. The footer insert strip appends a section after all existing sections
	it("footer section insert appends a section at the end", () => {
		cy.insert_doc(
			"Print Format",
			{
				name: PF_NAME,
				doc_type: "ToDo",
				print_format_builder_beta: 1,
				format_data: one_section_layout(),
			},
			true
		);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);
		cy.get("[data-pfb-section]", { timeout: 20000 }).should("have.length", 1);

		// The footer insert is rendered in <template #footer> of <draggable>,
		// so it lives in .sections-container but outside any .section-with-insert
		cy.get(".sections-container > .section-insert").click({ force: true });

		cy.get("[data-pfb-section]").should("have.length", 2);
	});

	// 8. Multiple inserts accumulate correctly
	it("inserting sections three times yields three sections on a blank canvas", () => {
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

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);
		cy.get(".sections-container", { timeout: 20000 }).should("be.visible");

		// Blank canvas starts with 0 sections — only the footer insert is present
		cy.get("[data-pfb-section]").should("have.length", 0);

		cy.get(".sections-container > .section-insert").click({ force: true });
		cy.get("[data-pfb-section]").should("have.length", 1);

		cy.get(".sections-container > .section-insert").click({ force: true });
		cy.get("[data-pfb-section]").should("have.length", 2);

		cy.get(".sections-container > .section-insert").click({ force: true });
		cy.get("[data-pfb-section]").should("have.length", 3);
	});

	// 9. Section insert is NOT hidden in clean-preview mode (the regression we fixed)
	//
	// The old code had:
	//   .pfb-clean-preview :deep(.section-insert) { display: none !important }
	// which hid the button when a live record was loaded. The fix removed that rule.
	// We verify the element is still in the DOM (not display:none) after simulating
	// preview mode by adding the class programmatically.
	it("section insert is not hidden when preview class is present on the canvas", () => {
		cy.insert_doc(
			"Print Format",
			{
				name: PF_NAME,
				doc_type: "ToDo",
				print_format_builder_beta: 1,
				format_data: one_section_layout(),
			},
			true
		);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);
		cy.get(".sections-container", { timeout: 20000 }).should("be.visible");

		// Simulate the canvas entering clean-preview mode
		cy.get(".print-format-main").then(($el) => {
			$el[0].classList.add("pfb-clean-preview");
		});

		// The insert strip must not be hidden with display:none
		cy.get(".section-insert").first().should("not.have.css", "display", "none");
	});
});
