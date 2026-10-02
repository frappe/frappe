// The list view's filter: a panel of rows on desktop, a bottom sheet of rows on a phone.

context("List filter", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
	});

	const applied = () =>
		cy
			.window()
			.its("cur_list.filter_area")
			.then((area) => area.get().map((f) => f.slice(1, 4)));

	describe("panel", () => {
		it("applies a filter as soon as it is complete", () => {
			cy.go_to_list("ToDo");
			cy.clear_filters();

			cy.open_list_filter();
			cy.pick_filter_field("Status");
			cy.get(".filter-popover .filter-field select").select("Closed");

			cy.get(".filter-selector .filter-label").should("have.text", "1");
			applied().should("deep.include", ["status", "=", "Closed"]);
			cy.get(".filter-popover .apply-filters").should("not.exist");
			// Status has a box in the toolbar, so the filter shows there too
			cy.window()
				.its("cur_list.page.fields_dict.status")
				.then((box) => expect(box.get_value()).to.eq("Closed"));
		});

		it("keeps an edit to a toolbar filter's row when the panel closes", () => {
			cy.go_to_list("ToDo");
			cy.clear_filters();
			cy.window()
				.its("cur_list.page.fields_dict.name")
				.then((box) => box.set_value("first"));

			cy.open_list_filter();
			cy.get('.filter-popover .filter-field input[data-fieldname="name"]')
				.should("have.value", "first")
				.clear()
				.type("second");
			cy.get(".layout-main-section").click("bottom");

			cy.get(".filter-popover").should("not.exist");
			cy.window()
				.its("cur_list.page.fields_dict.name")
				.then((box) => expect(box.get_value()).to.eq("second"));
		});

		it("a Check field filters only once Yes or No is chosen", () => {
			cy.go_to_list("Web Page");
			cy.clear_filters();

			cy.open_list_filter();
			cy.pick_filter_field("Published");
			cy.get(".filter-popover .filter-field select").should("have.value", "");
			applied().should("have.length", 0);

			cy.get(".filter-popover .filter-field select").select("No");
			applied().should("deep.include", ["published", "=", 0]);
		});
	});

	describe("sheet on a phone", { viewportWidth: 402, viewportHeight: 800 }, () => {
		const open_sheet = () => {
			cy.get(".filter-selector .filter-button").click();
			cy.get(".es-bottom-sheet").should("exist");
		};
		const footer_button = (label) => cy.contains(".es-bottom-sheet__footer button", label);

		beforeEach(() => {
			cy.go_to_list("ToDo");
			cy.clear_filters();
		});

		it("lists filters as rows and applies them on Apply", () => {
			open_sheet();
			cy.get(".es-bottom-sheet").should("contain", "No filters applied");

			footer_button("Add filter").click();
			cy.get(".es-bottom-sheet__title").should("have.text", "New filter");
			cy.get(".filter-sheet-edit .fieldname-select-area .es-combobox").click();
			cy.get(".es-bottom-sheet__subheader input").type("Status");
			cy.contains(".es-bottom-sheet__option:visible", /^Status$/).click();
			cy.get(".filter-sheet-edit .filter-field select").select("Closed");
			footer_button("Done").click();

			cy.get(".filter-sheet-row")
				.should("have.length", 1)
				.and("contain", "Status")
				.and("contain", "Closed");
			applied().should("have.length", 0);

			footer_button("Apply").click();
			cy.get(".es-bottom-sheet").should("not.exist");
			applied().should("deep.include", ["status", "=", "Closed"]);
		});

		it("picks a date and time in a calendar step, set on Done", () => {
			cy.window()
				.its("cur_list.filter_area")
				.then((area) => area.add([["ToDo", "creation", ">", "2026-01-01 00:00:00"]]));

			open_sheet();
			cy.get(".filter-sheet-row__edit").click();
			cy.get(".filter-sheet-edit .filter-field input")
				.invoke("val")
				.then((before) => {
					cy.get(".filter-sheet-edit .filter-field input").click();

					cy.get(".es-bottom-sheet__title").should("have.text", "Choose date and time");
					cy.get(".datepickers-container .datepicker.active").should("not.exist");
					cy.get(".filter-calendar .datepicker--button").click();
					footer_button("Done").click();

					cy.get(".es-bottom-sheet__title").should("have.text", "Edit filter");
					cy.get(".filter-sheet-edit .filter-field input")
						.invoke("val")
						.should("not.eq", before)
						.and("not.be.empty");
				});
		});

		it("shows option labels, forgets an abandoned filter and discards edits without Apply", () => {
			cy.window()
				.its("cur_list.filter_area")
				.then((area) => area.add([["ToDo", "creation", "Timespan", "last 7 days"]]));

			open_sheet();
			cy.get(".filter-sheet-row").should("have.length", 1).and("contain", "Last 7 Days");

			footer_button("Add filter").click();
			cy.get(".es-bottom-sheet__back").click();
			cy.get(".filter-sheet-row__edit").click();
			cy.get(".filter-sheet-edit .filter-box").should("have.length", 1);
			cy.get(".es-bottom-sheet__back").click();

			cy.get(".filter-sheet-row .es-button").click();
			cy.get(".es-bottom-sheet").should("contain", "No filters applied");
			cy.get(".es-bottom-sheet").trigger("keydown", { key: "Escape" });
			cy.get(".es-bottom-sheet").should("not.exist");
			applied().should("deep.include", ["creation", "Timespan", "last 7 days"]);
		});
	});
});
