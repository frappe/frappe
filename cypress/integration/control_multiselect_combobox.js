// Table MultiSelect, MultiSelectPills and MultiSelect with the combobox setting on.

const OTHER_USER = "multiselect_combobox@example.com";

context("Control MultiSelect (combobox)", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.set_value("System Settings", "System Settings", { enable_combobox_link_field: 1 });
		// a second user to pick; the search leaves out Administrator and Guest
		cy.insert_doc(
			"User",
			{ email: OTHER_USER, first_name: "Multiselect", send_welcome_email: 0 },
			true
		);
	});

	after(() => {
		cy.visit("/desk/website");
		cy.set_value("System Settings", "System Settings", { enable_combobox_link_field: 0 });
	});

	// without developer mode, the "leave site?" prompt blocks the test, so remove it
	afterEach(() => {
		cy.window().then((win) => {
			if (win.cur_frm) {
				win.removeEventListener("beforeunload", win.cur_frm.beforeUnloadListener, {
					capture: true,
				});
			}
		});
	});

	const trigger = (fieldname) =>
		cy.get(`.frappe-control[data-fieldname=${fieldname}] .es-combobox`).first();
	const panel = () => cy.get(".es-combobox__panel[data-state='open']");
	const search = () => panel().find(".es-combobox__input");
	const option = (text) =>
		panel()
			.find(".es-combobox__list [role='option']")
			.contains(text)
			.closest("[role='option']");
	const pills = (fieldname) =>
		cy.get(`.frappe-control[data-fieldname=${fieldname}] .es-combobox__pill:visible`);

	it("Table MultiSelect: ticks rows into child rows, keeps the panel open and removes a pill", () => {
		cy.new_form("User Group");
		cy.window().its("cur_frm.fields_dict.user_group_members.combobox").should("exist");
		const members = () =>
			cy
				.window()
				.its("cur_frm.doc.user_group_members")
				.then((rows) => rows.map((r) => r.user));

		trigger("user_group_members").click();
		search().type(OTHER_USER);
		option(OTHER_USER).click();
		// a tick keeps the panel open
		panel().should("exist");
		option(OTHER_USER).should("have.attr", "aria-selected", "true");
		members().should("deep.equal", [OTHER_USER]);

		// Enter ticks the highlighted row
		search().clear().type(Cypress.config("testUser"));
		panel().find(".es-combobox__list [role='option']").should("have.length", 1);
		search().type("{enter}");
		members().should("deep.equal", [OTHER_USER, Cypress.config("testUser")]);
		pills("user_group_members").should("have.length", 2);
		panel().find(".es-combobox__status").should("contain", "2 selected");

		// back to no search: the picked rows move under Selected
		search().clear();
		panel().find(".es-menu__group-label").first().should("have.text", "Selected");
		panel()
			.find(".es-menu__group")
			.first()
			.find("[role='option'][aria-selected='true']")
			.should("have.length", 2);

		// the × on a pill removes its row; the panel stays open
		pills("user_group_members").first().find(".es-combobox__pill-remove").click();
		members().should("deep.equal", [Cypress.config("testUser")]);
		panel().should("exist");

		search().type("{esc}");
		panel().should("not.exist");
	});

	it("MultiSelectPills and MultiSelect: a list, a comma string, free text and Backspace", () => {
		cy.window().its("frappe.sys_defaults").should("exist");
		cy.dialog({
			title: "Multi",
			fields: [
				// a plain first field, so no panel opens with the dialog
				{ fieldtype: "Data", fieldname: "note", label: "Note" },
				{
					fieldtype: "MultiSelectPills",
					fieldname: "pills",
					label: "Pills",
					options: ["Alpha", "Beta", "Gamma"],
				},
				{
					fieldtype: "MultiSelectPills",
					fieldname: "tags",
					label: "Tags",
					// ignores the typed text, like some app get_data functions
					get_data: () => ["Delta", "Echo"],
				},
				{
					fieldtype: "MultiSelect",
					fieldname: "colors",
					label: "Colors",
					options: ["Red", "Green"],
					default: "Green",
				},
				{
					fieldtype: "MultiSelect",
					fieldname: "emails",
					label: "Emails",
					ignore_validation: 1,
				},
			],
		}).as("dialog");
		cy.window().its("cur_dialog.display").should("eq", true);

		// MultiSelectPills: a list of values, in pick order
		trigger("pills").click();
		option("Beta").click();
		option("Alpha").click();
		cy.get("@dialog").should((d) =>
			expect(d.get_value("pills")).to.deep.equal(["Beta", "Alpha"])
		);
		// Backspace in the empty search removes the last pill
		search().type("{backspace}");
		cy.get("@dialog").should((d) => expect(d.get_value("pills")).to.deep.equal(["Beta"]));
		search().type("{esc}");
		panel().should("not.exist");

		// get_data rows are filtered by the typed text, and any typed text can be added
		trigger("tags").click();
		search().type("ech");
		panel().find(".es-combobox__list [role='option']").should("have.length", 1);
		search().clear().type("Foxtrot");
		panel().find(".es-combobox__footer").should("contain", 'Use "Foxtrot"');
		search().type("{enter}");
		cy.get("@dialog").should((d) => expect(d.get_value("tags")).to.deep.equal(["Foxtrot"]));
		search().type("{esc}");

		// MultiSelect: the default shows under Selected, and the value is a comma string
		pills("colors").should("have.length", 1).and("contain", "Green");
		trigger("colors").click();
		panel().find(".es-menu__group-label").first().should("have.text", "Selected");
		option("Red").click();
		cy.get("@dialog").should((d) => expect(d.get_value("colors")).to.equal("Green, Red"));
		search().type("{esc}");
		// as the classic control, a value outside the fixed list is refused
		cy.get("@dialog").then((d) => d.fields_dict.colors.set_value("Green, Purple"));
		cy.get("@dialog").should((d) => expect(d.get_value("colors")).to.equal(""));

		// free text: "Use …" adds the typed text and clears the search
		trigger("emails").click();
		search().type("someone@example.com");
		panel().find(".es-combobox__footer").should("contain", 'Use "someone@example.com"');
		search().type("{enter}");
		search().should("have.value", "");
		panel().should("exist");
		cy.get("@dialog").should((d) =>
			expect(d.get_value("emails")).to.equal("someone@example.com")
		);
		search().type("{esc}");
	});
});
