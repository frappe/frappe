// Cypress tests for the Print Format Builder.
//
// Each test generates its own unique PF_NAME and tears it down in
// afterEach, so Cypress retries and parallel runs never collide.

// ─── shared helpers ───────────────────────────────────────────────────────────

function pf_name() {
	return `Cypress PF ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
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

function builder_layout(sections = []) {
	return {
		sections,
		header: { columns: [{ label: "", fields: [] }] },
		footer: { columns: [{ label: "", fields: [] }] },
	};
}

function one_section_layout() {
	return JSON.stringify(
		builder_layout([{ label: "Alpha", columns: [{ label: "", fields: [] }] }])
	);
}

function insert_builder_format(name, sections = []) {
	cy.insert_doc(
		"Print Format",
		{
			name,
			doc_type: "ToDo",
			print_format_builder_beta: 1,
			format_data: JSON.stringify(builder_layout(sections)),
		},
		true
	);
}

// ─── Create flow ──────────────────────────────────────────────────────────────

context("Print Format Builder — create flow", () => {
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

	// 1. The route no longer creates anything on its own — it sends you to the list
	it("redirects to the Print Format list when opened without a format", () => {
		cy.visit("/app/print-format-builder");
		cy.location("pathname", { timeout: 20000 }).should(
			"match",
			/^\/(app|desk)\/print-format(\/view\/list)?$/
		);
	});

	// 2. The Print Format form is where a format is created, and it opens the builder
	it("opens the builder from the Print Format form", () => {
		insert_builder_format(PF_NAME);

		cy.visit(`/app/print-format/${encodeURIComponent(PF_NAME)}`);
		cy.get(".page-actions", { timeout: 20000 }).contains("button", "Edit Format").click();

		cy.location("pathname", { timeout: 20000 }).should(
			"match",
			/\/(app|desk)\/print-format-builder\//
		);
		cy.get(".print-format-main", { timeout: 20000 }).should("exist");
	});

	// 2b. The New dialog: "HTML" creates a custom format and opens the form
	it("creates an HTML format from the dialog and opens the form", () => {
		cy.visit("/app/print-format");
		cy.get(".page-head .primary-action", { timeout: 30000 }).should("be.visible").click();
		cy.get_open_dialog().should("contain", "New Print Format");

		// scope fills to the dialog — the list page has its own hidden doc_type field
		cy.get_open_dialog().within(() => {
			cy.fill_field("doc_type", "ToDo", "Link");
			cy.fill_field("print_format_name", PF_NAME, "Data");
			cy.fill_field("start_with", "HTML", "Select");
			cy.findByRole("button", { name: "Create" }).click();
		});

		// the form route carries the created doc's real name — read it back instead
		// of trusting the typed string (cy.type can drop characters)
		cy.location("pathname", { timeout: 20000 }).should(
			"match",
			/\/(app|desk)\/print-format\/(?!view\/)/
		);
		cy.location("pathname").then((path) => {
			const created = decodeURIComponent(path.split("/").pop());
			expect(created).to.contain("Cypress PF");
			PF_NAME = created;
			cy.call("frappe.client.get_value", {
				doctype: "Print Format",
				filters: { name: created },
				fieldname: ["custom_format", "print_format_builder_beta", "html"],
			}).then((r) => {
				expect(Number(r.message.custom_format)).to.equal(1);
				expect(Number(r.message.print_format_builder_beta)).to.equal(0);
				expect(r.message.html).to.contain("print-format");
			});
		});
	});

	// 2c. The New dialog: "Builder" creates a builder format and opens the builder
	it("creates a builder format from the dialog and opens the builder", () => {
		cy.visit("/app/print-format");
		cy.get(".page-head .primary-action", { timeout: 30000 }).should("be.visible").click();
		cy.get_open_dialog().should("contain", "New Print Format");

		// scope fills to the dialog — the list page has its own hidden doc_type field
		cy.get_open_dialog().within(() => {
			cy.fill_field("doc_type", "ToDo", "Link");
			cy.fill_field("print_format_name", PF_NAME, "Data");
			// start_with defaults to Builder
			cy.findByRole("button", { name: "Create" }).click();
		});

		// the builder route carries the created doc's real name — read it back instead
		// of trusting the typed string (cy.type can drop characters)
		cy.location("pathname", { timeout: 20000 }).should(
			"match",
			/\/(app|desk)\/print-format-builder\//
		);
		cy.location("pathname").then((path) => {
			const created = decodeURIComponent(path.split("/").pop());
			expect(created).to.contain("Cypress PF");
			PF_NAME = created;
			cy.call("frappe.client.get_value", {
				doctype: "Print Format",
				filters: { name: created },
				fieldname: ["custom_format", "print_format_builder_beta"],
			}).then((r) => {
				expect(Number(r.message.custom_format)).to.equal(0);
				expect(Number(r.message.print_format_builder_beta)).to.equal(1);
			});
		});
	});

	// 3. Loading the builder for an existing format and saving a change
	it("loads the builder and Save persists a margin change", () => {
		cy.visit("/app");

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

		cy.intercept(
			"POST",
			"api/method/frappe.printing.doctype.print_format.print_format.apply_draft"
		).as("save");
		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get(".pfb-margin-grid", { timeout: 30000 }).should("be.visible");

		cy.get(".freeze").should("not.exist");
		cy.get('[data-testid="page-status"]').should("not.be.visible");

		cy.contains(".pfb-margin-cell label", "Top")
			.closest(".pfb-margin-cell")
			.find('input[type="number"]')
			.clear()
			.type("9")
			.trigger("change")
			.blur();

		cy.contains(".page-actions .primary-action", "Save & Apply").click({ force: true });
		cy.wait("@save").then((interception) => {
			expect(interception.response.statusCode).to.equal(200);
			expect(Number(interception.response.body.message.margin_top)).to.equal(9);
		});
		cy.get('[data-testid="page-status"]').should("not.be.visible");
	});

	// 4. Layers tab: clicking a section scrolls to it and selects it
	it("layers tab selects a section on click", () => {
		cy.visit("/app");

		insert_builder_format(PF_NAME, [
			{ label: "Alpha", columns: [{ label: "", fields: [] }] },
			{ label: "Beta", columns: [{ label: "", fields: [] }] },
		]);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get(".es-tabs__tab[data-tab='layers']", { timeout: 30000 }).click();
		cy.contains(".pfb-tree-row", "Beta").click();

		cy.get(".pfb-inspector").should("contain", "Section");
		cy.get(".pfb-inspector").should("contain", "Beta");
		cy.contains(".pfb-tree-row", "Beta").should("have.class", "active");
	});

	// 5. Field inspector breadcrumb navigates back to parent section
	it("field breadcrumb navigates to parent section", () => {
		cy.visit("/app");

		insert_builder_format(PF_NAME, [
			{
				label: "Details",
				columns: [
					{
						label: "",
						fields: [
							{ fieldtype: "Data", fieldname: "description", label: "Description" },
						],
					},
				],
			},
		]);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get(".es-tabs__tab[data-tab='layers']", { timeout: 30000 }).click();
		cy.contains(".pfb-tree-row", "Details").click();

		cy.get(".print-format-container").click();
		cy.contains("[data-pfb-section]", "Details").find(".field").first().click({ force: true });

		cy.get(".pfb-breadcrumb").should("be.visible");
		cy.get(".pfb-breadcrumb-name").should("contain", "Details");

		cy.get(".pfb-breadcrumb-btn").click();
		cy.get(".pfb-inspector").should("contain", "Section");
		cy.get(".pfb-inspector").should("contain", "Details");
		cy.get(".pfb-breadcrumb").should("not.exist");
	});

	// 6. Settings (inspector): font size change is reflected in canvas
	it("font size change applies to canvas preview", () => {
		cy.visit("/app");

		insert_builder_format(PF_NAME, []);

		cy.intercept(
			"POST",
			"api/method/frappe.printing.doctype.print_format.print_format.apply_draft"
		).as("save");
		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get(".pfb-margin-grid", { timeout: 30000 }).should("be.visible");

		cy.contains("label", "Font Size")
			.closest(".form-group")
			.find("input")
			.clear()
			.type("18")
			.trigger("change")
			.blur();

		cy.get(".pfb-body").should(($el) => {
			const fs = parseInt($el.css("font-size"), 10);
			expect(fs).to.equal(18);
		});
	});

	// 7. Table layout: field_borders renders a grid with a column divider
	it("table layout renders grid borders in the canvas", () => {
		cy.visit("/app");

		insert_builder_format(PF_NAME, [
			{
				label: "Grid",
				field_borders: true,
				columns: [
					{
						fields: [
							{ fieldtype: "Data", fieldname: "description", label: "Description" },
						],
					},
					{ fields: [{ fieldtype: "Data", fieldname: "status", label: "Status" }] },
				],
			},
		]);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get(".section--grid", { timeout: 30000 }).should("be.visible");
		cy.get(".section--grid .column")
			.first()
			.should(($el) => {
				expect(parseInt($el.css("border-right-width"), 10)).to.be.greaterThan(0);
			});
	});

	// 8. Settings (inspector): label color uses the Frappe Color control and persists on save
	it("settings label color persists on save", () => {
		cy.visit("/app");

		insert_builder_format(PF_NAME, []);

		cy.intercept(
			"POST",
			"api/method/frappe.printing.doctype.print_format.print_format.apply_draft"
		).as("save");
		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get(".pfb-margin-grid", { timeout: 30000 }).should("be.visible");

		// The color field is rendered with Frappe's ControlColor (adds .selected-color swatch)
		cy.get('[data-fieldname="label_color"] .selected-color').should("exist");

		cy.get('[data-fieldname="label_color"] input:visible')
			.clear()
			.type("#c0392b")
			.trigger("change")
			.blur();

		cy.contains(".page-actions .primary-action", "Save & Apply").click({ force: true });
		cy.wait("@save").then((interception) => {
			expect(interception.response.statusCode).to.equal(200);
			expect(interception.response.body.message.label_color).to.equal("#c0392b");
		});
	});

	// 9. Selecting a repeater field exposes per-column width and color controls
	it("repeater inspector shows column width and color controls", () => {
		cy.visit("/app");

		insert_builder_format(PF_NAME, [
			{
				label: "Rep Section",
				columns: [
					{
						label: "",
						fields: [
							{
								fieldtype: "Repeater",
								fieldname: "rep1",
								label: "Rep",
								repeater_columns: [{ template: [], align: "left" }],
							},
						],
					},
				],
			},
		]);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get("[data-pfb-section]", { timeout: 30000 }).should("be.visible");
		cy.contains("[data-pfb-section]", "Rep Section")
			.find(".field")
			.first()
			.click({ force: true });

		cy.get(".pfb-inspector").should("contain", "Repeater");
		cy.get(".pfb-inspector").should("contain", "Columns");
		cy.get(".pfb-inspector").should("contain", "Color");
		cy.get(".pfb-inspector .pfb-rep-col-color .selected-color").should("exist");
		cy.get(".pfb-inspector .pfb-col-width-input").should("exist");
	});

	// 10. Inspector header shows the doctype field's label, not a custom print label
	it("field inspector header keeps the doctype label after a custom rename", () => {
		cy.visit("/app");

		insert_builder_format(PF_NAME, [
			{
				label: "Details",
				columns: [
					{
						label: "",
						fields: [{ fieldtype: "Date", fieldname: "date", label: "Deadline" }],
					},
				],
			},
		]);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get("[data-pfb-section]", { timeout: 30000 }).should("be.visible");
		cy.contains("[data-pfb-section]", "Details").find(".field").first().click({ force: true });

		cy.get(".pfb-inspector").should("contain", "Due Date");
		cy.get(".pfb-inspector").should("not.contain", "Deadline");
		cy.contains(".pfb-insp-row", "Label")
			.find("input.pfb-insp-input")
			.should("have.value", "Deadline");
	});

	// 11. Center/right align wins over a stale Spacing value, and the now-irrelevant
	// Spacing control is hidden instead of silently conflicting with it
	it("field align overrides a conflicting label-justify setting", () => {
		cy.visit("/app");

		// the left-right/align classes only render in live preview mode, so
		// the doctype needs at least one record to auto-preview
		cy.insert_doc("ToDo", { description: "pfb align override preview" }, true);

		insert_builder_format(PF_NAME, [
			{
				label: "Details",
				field_orientation: "left-right",
				columns: [
					{
						label: "",
						fields: [
							{
								fieldtype: "Date",
								fieldname: "date",
								label: "Due Date",
								align: "center",
								label_justify: "space-between",
							},
						],
					},
				],
			},
		]);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get("[data-pfb-section]", { timeout: 30000 }).should("be.visible");
		cy.contains("[data-pfb-section]", "Details")
			.find(".field.left-right")
			.as("field")
			.click({ force: true });

		cy.get("@field").should("have.css", "justify-content", "center");
		cy.get(".pfb-inspector").should("not.contain", "Spacing");
	});
});

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

	// 7. New format with no format_data shows the "How do you want to start?" screen
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

	// 8. Format with saved format_data skips the setup screen entirely
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

		cy.get(".sections-container", { timeout: 20000 }).should("be.visible");
		cy.get(".pfb-setup").should("not.exist");
	});

	// 9. "Start blank" dismisses the setup screen and creates an empty canvas
	it("Start blank dismisses setup and shows empty canvas", () => {
		cy.insert_doc(
			"Print Format",
			{ name: PF_NAME, doc_type: "ToDo", print_format_builder_beta: 1 },
			true
		);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get(".pfb-setup", { timeout: 20000 }).should("be.visible");
		cy.contains(".pfb-setup-option-label", "Start blank").click();

		cy.get(".pfb-setup").should("not.exist");
		cy.get(".body-empty").should("be.visible");
		// blank canvas — no body sections
		cy.get(".sections-container [data-pfb-section]").should("have.length", 0);

		// explicitly save and verify the saved layout has no sections
		cy.intercept(
			"POST",
			"api/method/frappe.printing.doctype.print_format.print_format.apply_draft"
		).as("save");
		cy.contains(".page-actions .primary-action", "Save & Apply").click({ force: true });
		cy.wait("@save").then((interception) => {
			expect(interception.response.statusCode).to.equal(200);
			const layout = JSON.parse(interception.response.body.message.format_data);
			expect(layout.sections).to.deep.equal([]);
		});
	});

	// 10. "Start from default" dismisses the setup screen and populates sections
	it("Start from default dismisses setup and fills canvas with document fields", () => {
		cy.insert_doc(
			"Print Format",
			{ name: PF_NAME, doc_type: "ToDo", print_format_builder_beta: 1 },
			true
		);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get(".pfb-setup", { timeout: 20000 }).should("be.visible");
		cy.contains(".pfb-setup-option-label", "Start from default").click();

		cy.get(".pfb-setup").should("not.exist");
		// body sections are populated from ToDo's default fields
		cy.get(".sections-container [data-pfb-section]", { timeout: 10000 }).should(
			"have.length.greaterThan",
			0
		);

		// explicitly save and verify the saved layout has sections
		cy.intercept(
			"POST",
			"api/method/frappe.printing.doctype.print_format.print_format.apply_draft"
		).as("save");
		cy.contains(".page-actions .primary-action", "Save & Apply").click({ force: true });
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

	// 11. Section insert element exists in DOM (opacity:0, not display:none)
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

		cy.get(".section-insert").should("exist");
		cy.get(".section-insert").first().should("not.have.css", "display", "none");
		cy.get(".section-insert-btn").first().should("contain", "Add Section");
	});

	// 12. Clicking the insert strip before a section adds a new section above it
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
		cy.get(".sections-container [data-pfb-section]", { timeout: 20000 }).should(
			"have.length",
			1
		);

		cy.get(".section-with-insert .section-insert-btn").first().click({ force: true });

		cy.get(".sections-container [data-pfb-section]").should("have.length", 2);
	});

	// 13. The footer insert strip appends a section after all existing sections
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
		cy.get(".sections-container [data-pfb-section]", { timeout: 20000 }).should(
			"have.length",
			1
		);

		cy.get(".sections-container > .section-insert .section-insert-btn").click({ force: true });

		cy.get(".sections-container [data-pfb-section]").should("have.length", 2);
	});

	// 14. Multiple inserts accumulate correctly
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
		cy.get(".body-empty", { timeout: 20000 }).should("be.visible");
		cy.get(".sections-container [data-pfb-section]").should("have.length", 0);

		// blank canvas: the first section is added via the empty-state CTA
		cy.get(".body-empty").click({ force: true });
		cy.get(".sections-container [data-pfb-section]").should("have.length", 1);

		cy.get(".sections-container > .section-insert .section-insert-btn").click({ force: true });
		cy.get(".sections-container [data-pfb-section]").should("have.length", 2);

		cy.get(".sections-container > .section-insert .section-insert-btn").click({ force: true });
		cy.get(".sections-container [data-pfb-section]").should("have.length", 3);
	});

	// 15. Section insert is NOT hidden in clean-preview mode (regression guard)
	//
	// The old code had:
	//   .pfb-clean-preview :deep(.section-insert) { display: none !important }
	// which hid the button when a live record was loaded. The fix removed that rule.
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

		cy.get(".print-format-main").then(($el) => {
			$el[0].classList.add("pfb-clean-preview");
		});

		cy.get(".section-insert").first().should("not.have.css", "display", "none");
	});
});

// ─── Column width resize ──────────────────────────────────────────────────────

context("Print Format Builder — column width resize", () => {
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

	function two_column_section() {
		return [
			{
				label: "Two Cols",
				columns: [
					{
						label: "",
						fields: [
							{ fieldtype: "Data", fieldname: "description", label: "Description" },
						],
					},
					{
						label: "",
						fields: [{ fieldtype: "Data", fieldname: "status", label: "Status" }],
					},
				],
			},
		];
	}

	function drag_handle(selector, dx) {
		cy.get(selector)
			.first()
			.then(($h) => {
				const rect = $h[0].getBoundingClientRect();
				const x = rect.left + rect.width / 2;
				const y = rect.top + rect.height / 2;
				const opts = { button: 0, pointerId: 1, pointerType: "mouse", isPrimary: true };
				cy.wrap($h).trigger("pointerdown", { ...opts, clientX: x, clientY: y });
				cy.get("body")
					.trigger("pointermove", { ...opts, clientX: x + dx, clientY: y })
					.trigger("pointerup", { ...opts, clientX: x + dx, clientY: y });
			});
	}

	// 16. One handle per column boundary; none for a single-column section
	it("renders a resize handle only between section columns", () => {
		insert_builder_format(PF_NAME, [
			...two_column_section(),
			{ label: "One Col", columns: [{ label: "", fields: [] }] },
		]);

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);
		cy.get(".sections-container", { timeout: 20000 }).should("be.visible");

		cy.contains("[data-pfb-section]", "Two Cols")
			.find(".col-width-handle")
			.should("have.length", 1);
		cy.contains("[data-pfb-section]", "One Col")
			.find(".col-width-handle")
			.should("have.length", 0);
	});

	// 17. Dragging the boundary applies flex ratios on the canvas and persists
	// column widths in format_data on save
	it("dragging the section column handle resizes and persists widths", () => {
		insert_builder_format(PF_NAME, two_column_section());

		cy.intercept(
			"POST",
			"api/method/frappe.printing.doctype.print_format.print_format.apply_draft"
		).as("save");
		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);
		cy.get(".sections-container", { timeout: 20000 }).should("be.visible");

		cy.get(".sections-container .column").first().should("not.have.attr", "style");

		cy.get(".sections-container .section-columns")
			.first()
			.then(($sc) => {
				const total = $sc[0].getBoundingClientRect().width;
				drag_handle(".sections-container .col-width-handle", -total * 0.2);
			});

		cy.get(".sections-container .column")
			.first()
			.should(($el) => {
				const flex_grow = parseInt($el.css("flex-grow"), 10);
				expect(flex_grow).to.be.within(25, 35);
			});
		cy.get(".sections-container .column")
			.eq(1)
			.should(($el) => {
				const flex_grow = parseInt($el.css("flex-grow"), 10);
				expect(flex_grow).to.be.within(65, 75);
			});

		cy.contains(".page-actions .primary-action", "Save & Apply").click({ force: true });
		cy.wait("@save").then((interception) => {
			expect(interception.response.statusCode).to.equal(200);
			const layout = JSON.parse(interception.response.body.message.format_data);
			const cols = layout.sections[0].columns;
			// the container gap is excluded from measured widths and each width
			// is rounded, so the sum lands a few points under 100
			expect(cols[0].width).to.be.within(23, 38);
			expect(cols[1].width).to.be.within(60, 77);
			expect(cols[0].width + cols[1].width).to.be.within(88, 100);
		});
	});

	// 18. Dragging respects the 10% minimum per column
	it("section column resize clamps at the 10% minimum", () => {
		insert_builder_format(PF_NAME, two_column_section());

		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);
		cy.get(".sections-container", { timeout: 20000 }).should("be.visible");

		drag_handle(".sections-container .col-width-handle", -5000);

		cy.get(".sections-container .column")
			.first()
			.should(($el) => {
				expect(parseInt($el.css("flex-grow"), 10)).to.be.at.least(10);
			});
	});

	// 19. Dragging a table column header boundary transfers width between
	// neighbours and persists via table_columns
	it("dragging the table column handle resizes and persists widths", () => {
		// table markup (and its resize handles) only renders in live preview
		// mode, so the doctype needs at least one record to auto-preview
		cy.insert_doc("ToDo", { description: "pfb column resize preview" }, true);

		insert_builder_format(PF_NAME, [
			{
				label: "Tbl",
				columns: [
					{
						label: "",
						fields: [
							{
								fieldtype: "Table",
								fieldname: "assignments_cy1",
								label: "Items",
								custom: 1,
								table_columns: [
									{
										fieldname: "a",
										label: "Alpha",
										fieldtype: "Data",
										width: 50,
									},
									{
										fieldname: "b",
										label: "Beta",
										fieldtype: "Data",
										width: 50,
									},
								],
							},
						],
					},
				],
			},
		]);

		cy.intercept(
			"POST",
			"api/method/frappe.printing.doctype.print_format.print_format.apply_draft"
		).as("save");
		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);
		cy.get(".sections-container", { timeout: 20000 }).should("be.visible");

		cy.get(".sections-container th.column-header").should("have.length", 2);
		cy.get(".sections-container .col-resize-handle").should("have.length", 1);

		cy.get(".sections-container table.table")
			.first()
			.then(($t) => {
				const total = $t[0].getBoundingClientRect().width;
				drag_handle(".sections-container .col-resize-handle", -total * 0.2);
			});

		cy.contains(".page-actions .primary-action", "Save & Apply").click({ force: true });
		cy.wait("@save").then((interception) => {
			expect(interception.response.statusCode).to.equal(200);
			const layout = JSON.parse(interception.response.body.message.format_data);
			const fields = layout.sections.flatMap((s) => s.columns).flatMap((c) => c.fields);
			const table = fields.find((f) => f.fieldtype === "Table");
			expect(table, "table field survived").to.exist;
			expect(table.table_columns[0].width).to.be.within(25, 35);
			expect(table.table_columns[1].width).to.be.within(65, 75);
			expect(table.table_columns[0].width + table.table_columns[1].width).to.equal(100);
		});
	});
});

// ─── Image and Barcode blocks ─────────────────────────────────────────────────

context("Print Format Builder — image and barcode blocks", () => {
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

	// Regression: serialize_layout must not strip image/barcode props on save
	it("image and barcode props survive the save round-trip", () => {
		insert_builder_format(PF_NAME, [
			{
				label: "Media",
				columns: [
					{
						label: "",
						fields: [
							{
								fieldtype: "Image",
								fieldname: "image_cy1",
								label: "Logo",
								custom: 1,
								image_url: "/assets/frappe/images/frappe-framework-logo.svg",
								width: "40mm",
								align: "center",
							},
							{
								fieldtype: "Barcode",
								fieldname: "barcode_cy1",
								label: "",
								custom: 1,
								barcode_value: "CY-TEST-1",
								barcode_format: "CODE128",
								show_text: true,
								width: "200px",
							},
						],
					},
				],
			},
		]);

		cy.intercept(
			"POST",
			"api/method/frappe.printing.doctype.print_format.print_format.apply_draft"
		).as("save");
		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);
		cy.get(".sections-container", { timeout: 20000 }).should("be.visible");

		// both blocks render in the canvas
		cy.get('.field img[src*="frappe-framework-logo"]').should("exist");

		cy.contains(".page-actions .primary-action", "Save & Apply").click({ force: true });
		cy.wait("@save").then((interception) => {
			expect(interception.response.statusCode).to.equal(200);
			const layout = JSON.parse(interception.response.body.message.format_data);
			const fields = layout.sections.flatMap((s) => s.columns).flatMap((c) => c.fields);

			const img = fields.find((f) => f.fieldtype === "Image");
			expect(img, "image field survived").to.exist;
			expect(img).to.include({
				custom: 1,
				image_url: "/assets/frappe/images/frappe-framework-logo.svg",
				width: "40mm",
				align: "center",
			});

			const bar = fields.find((f) => f.fieldtype === "Barcode");
			expect(bar, "barcode field survived").to.exist;
			expect(bar).to.include({
				custom: 1,
				barcode_value: "CY-TEST-1",
				barcode_format: "CODE128",
				show_text: true,
				width: "200px",
			});
		});
	});
});

// ─── selection & spacing ────────────────────────────────────────────────────────

context("Print Format Builder — selection & spacing", () => {
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

	function three_field_format(name) {
		insert_builder_format(name, [
			{
				label: "Alpha",
				columns: [
					{
						label: "",
						fields: [
							{ fieldtype: "Data", fieldname: "description", label: "Description" },
							{ fieldtype: "Data", fieldname: "status", label: "Status" },
							{ fieldtype: "Data", fieldname: "priority", label: "Priority" },
						],
					},
				],
			},
		]);
	}

	// 1. Shift-click selects a contiguous range
	it("shift-click selects a range of fields", () => {
		three_field_format(PF_NAME);
		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get("[data-pfb-section] .field", { timeout: 30000 }).should("have.length", 3);
		cy.get("[data-pfb-section] .field").eq(0).click({ force: true });
		cy.get("[data-pfb-section] .field").eq(2).click({ shiftKey: true, force: true });

		cy.get(".field--selected").should("have.length", 3);
		cy.get(".pfb-inspector").should("contain", "Selection").and("contain", "3 fields");
	});

	// 2. Ctrl/Cmd-click toggles fields individually
	it("cmd/ctrl-click toggles individual fields", () => {
		three_field_format(PF_NAME);
		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get("[data-pfb-section] .field", { timeout: 30000 }).eq(0).click({ force: true });
		cy.get("[data-pfb-section] .field").eq(1).click({ ctrlKey: true, force: true });
		cy.get(".field--selected").should("have.length", 2);

		// toggle the first one back off
		cy.get("[data-pfb-section] .field").eq(0).click({ ctrlKey: true, force: true });
		cy.get(".field--selected").should("have.length", 1);
	});

	// 3. Bulk "Remove selected" deletes every selected field
	it("bulk Remove selected deletes the selected fields", () => {
		three_field_format(PF_NAME);
		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get("[data-pfb-section] .field", { timeout: 30000 }).eq(0).click({ force: true });
		cy.get("[data-pfb-section] .field").eq(1).click({ ctrlKey: true, force: true });
		cy.get(".field--selected").should("have.length", 2);

		cy.contains(".es-button", "Remove selected").click();

		cy.get("[data-pfb-section] .field:visible").should("have.length", 1);
		cy.get(".field--selected").should("have.length", 0);
	});

	// 4. Dragging the padding handle grows the section padding
	it("padding handle drags to add section padding", () => {
		three_field_format(PF_NAME);
		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get(".es-tabs__tab[data-tab='layers']", { timeout: 30000 }).click();
		cy.contains(".pfb-tree-row", "Alpha").click();

		cy.get(".pfb-spacing-padding .pfb-space-grip-top").then(($g) => {
			const r = $g[0].getBoundingClientRect();
			const cx = r.x + r.width / 2;
			const cyv = r.y + r.height / 2;
			cy.wrap($g).trigger("pointerdown", {
				clientX: cx,
				clientY: cyv,
				button: 0,
				force: true,
			});
			cy.get("body").trigger("pointermove", { clientX: cx, clientY: cyv + 40, button: 0 });
			cy.get("body").trigger("pointerup", { clientX: cx, clientY: cyv + 40, force: true });
		});

		cy.get(".pfb-section-active .print-format-section").should(($s) => {
			expect(parseInt($s.css("padding-top"), 10)).to.be.greaterThan(10);
		});
	});

	// 5. The border-radius handle appears on a selected section and drags
	it("border-radius handle rounds the section corners", () => {
		three_field_format(PF_NAME);
		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);

		cy.get(".es-tabs__tab[data-tab='layers']", { timeout: 30000 }).click();
		cy.contains(".pfb-tree-row", "Alpha").click();

		cy.get(".pfb-radius-handle").should("exist");
		cy.get(".pfb-radius-handle").then(($h) => {
			const r = $h[0].getBoundingClientRect();
			const cx = r.x + r.width / 2;
			const cyv = r.y + r.height / 2;
			cy.wrap($h).trigger("pointerdown", {
				clientX: cx,
				clientY: cyv,
				button: 0,
				force: true,
			});
			cy.get("body").trigger("pointermove", {
				clientX: cx + 30,
				clientY: cyv + 30,
				button: 0,
			});
			cy.get("body").trigger("pointerup", {
				clientX: cx + 30,
				clientY: cyv + 30,
				force: true,
			});
		});

		cy.get(".pfb-section-active .print-format-section").should(($s) => {
			expect(parseInt($s.css("border-top-left-radius"), 10)).to.be.greaterThan(12);
		});
	});
});

// ─── Draft / Save & Apply ─────────────────────────────────────────────────────

const DISCARD_BTN = `.custom-actions [data-label="${encodeURIComponent("Discard Draft")}"]`;

context("Print Format Builder — draft and Save & Apply", () => {
	let PF_NAME;

	before(() => {
		cy.login();
		cy.visit("/app");
	});

	beforeEach(() => {
		PF_NAME = `_Test PFB Draft ${Math.floor(Math.random() * 1e6)}`;
		insert_builder_format(PF_NAME, []);
		cy.visit(`/app/print-format-builder/${encodeURIComponent(PF_NAME)}`);
		cy.get(".pfb-margin-grid", { timeout: 30000 }).should("be.visible");
		cy.get(".freeze").should("not.exist");
	});

	function set_margin_top(value) {
		cy.contains(".pfb-margin-cell label", "Top")
			.closest(".pfb-margin-cell")
			.find('input[type="number"]')
			.clear()
			.type(value)
			.trigger("change")
			.blur();
	}

	it("autosaves into the draft without changing what prints", () => {
		cy.intercept(
			"POST",
			"api/method/frappe.printing.doctype.print_format.print_format.save_draft"
		).as("draft");

		cy.get('[data-testid="page-status"]').should("not.be.visible");
		cy.get(DISCARD_BTN).should("not.be.visible");

		set_margin_top("17");

		cy.wait("@draft").its("response.statusCode").should("eq", 200);
		cy.get('[data-testid="page-status"]').should("contain", "Draft");
		cy.get(DISCARD_BTN).should("be.visible");

		// the live format is untouched until Save & Apply
		cy.call("frappe.client.get_value", {
			doctype: "Print Format",
			filters: { name: PF_NAME },
			fieldname: ["margin_top", "draft_data"],
		}).then((r) => {
			expect(Number(r.message.margin_top)).to.not.equal(17);
			expect(JSON.parse(r.message.draft_data).margin_top).to.equal(17);
		});
	});

	it("Save & Apply copies the draft onto the format and clears it", () => {
		cy.intercept(
			"POST",
			"api/method/frappe.printing.doctype.print_format.print_format.apply_draft"
		).as("apply");

		set_margin_top("19");
		cy.get('[data-testid="page-status"]').should("contain", "Draft");

		cy.contains(".page-actions .primary-action", "Save & Apply").click({ force: true });
		cy.wait("@apply").its("response.statusCode").should("eq", 200);

		cy.get('[data-testid="page-status"]').should("not.be.visible");
		cy.get(DISCARD_BTN).should("not.be.visible");

		cy.call("frappe.client.get_value", {
			doctype: "Print Format",
			filters: { name: PF_NAME },
			fieldname: ["margin_top", "draft_data"],
		}).then((r) => {
			expect(Number(r.message.margin_top)).to.equal(19);
			expect(r.message.draft_data).to.be.oneOf([null, ""]);
		});
	});

	it("keeps Typst block markup through Save & Apply", () => {
		const TYPST_PF_NAME = `${PF_NAME} Typst`;
		cy.insert_doc("Print Format", {
			name: TYPST_PF_NAME,
			doc_type: "ToDo",
			print_format_builder_beta: 1,
			pdf_generator: "Typst",
			format_data: JSON.stringify(
				builder_layout([
					{
						label: "",
						columns: [
							{
								label: "",
								fields: [
									{
										label: "Typst",
										fieldname: "typst_block_t",
										fieldtype: "Typst",
										custom: 1,
										typst: "Task: {{ doc.description }}",
									},
								],
							},
						],
					},
				])
			),
		});
		cy.visit(`/app/print-format-builder/${encodeURIComponent(TYPST_PF_NAME)}`);
		cy.get(".typst-block-source", { timeout: 30000 }).should("contain", "doc.description");

		cy.intercept(
			"POST",
			"api/method/frappe.printing.doctype.print_format.print_format.apply_draft"
		).as("apply");
		set_margin_top("18");
		cy.get('[data-testid="page-status"]').should("contain", "Draft");
		cy.contains(".page-actions .primary-action", "Save & Apply").click({ force: true });
		cy.wait("@apply").its("response.statusCode").should("eq", 200);

		cy.call("frappe.client.get_value", {
			doctype: "Print Format",
			filters: { name: TYPST_PF_NAME },
			fieldname: ["format_data"],
		}).then((r) => {
			expect(r.message.format_data).to.contain("Task: {{ doc.description }}");
		});
	});

	it("Discard Draft throws the draft away and leaves the format as it prints", () => {
		cy.intercept(
			"POST",
			"api/method/frappe.printing.doctype.print_format.print_format.discard_draft"
		).as("discard");

		set_margin_top("23");
		cy.get('[data-testid="page-status"]').should("contain", "Draft");

		cy.get(DISCARD_BTN).click({ force: true });
		cy.get(".modal-footer .btn-modal-primary:visible").click();
		cy.wait("@discard").its("response.statusCode").should("eq", 200);

		cy.get('[data-testid="page-status"]').should("not.be.visible");
		cy.get(DISCARD_BTN).should("not.be.visible");

		cy.call("frappe.client.get_value", {
			doctype: "Print Format",
			filters: { name: PF_NAME },
			fieldname: ["margin_top", "draft_data"],
		}).then((r) => {
			expect(Number(r.message.margin_top)).to.not.equal(23);
			expect(r.message.draft_data).to.be.oneOf([null, ""]);
		});
	});

	it("reopening the builder shows the draft, not what prints", () => {
		set_margin_top("29");
		cy.get('[data-testid="page-status"]').should("contain", "Draft");

		cy.reload();
		cy.get(".pfb-margin-grid", { timeout: 30000 }).should("be.visible");

		cy.get('[data-testid="page-status"]').should("contain", "Draft");
		cy.contains(".pfb-margin-cell label", "Top")
			.closest(".pfb-margin-cell")
			.find('input[type="number"]')
			.should("have.value", "29");
	});
});
