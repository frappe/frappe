// The Autocomplete field with the combobox setting on: control_autocomplete.js
// scenarios through the combobox panel, plus free text and set_data.

context("Control Autocomplete (combobox)", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.set_combobox_setting(true);
	});

	after(() => {
		cy.visit("/desk/website");
		cy.set_combobox_setting(false);
	});

	beforeEach(() => {
		cy.visit("/desk/website");
	});

	const make_dialog = (fieldname, options, extra = {}) => {
		cy.window().its("frappe.sys_defaults").should("exist");
		const dialog = cy.dialog({
			title: "Autocomplete",
			fields: [
				{
					label: "Select an option",
					fieldname,
					fieldtype: "Autocomplete",
					options,
					...extra,
				},
			],
		});
		cy.window().its("cur_dialog.display").should("eq", true);
		return dialog;
	};
	const field_input = (fieldname) =>
		cy.get(`.frappe-control[data-fieldname=${fieldname}] .es-combobox input`);
	const panel = () => cy.get(".es-combobox__panel[data-state='open']");
	const search = () => panel().find(".es-combobox__input");

	it("is the combobox control and picks a typed match with Enter", () => {
		make_dialog("ac1", ["Option 1", "Option 2", "Option 3"]).as("dialog");
		cy.get("@dialog").then((dialog) => {
			expect(dialog.get_field("ac1").combobox).to.exist;
		});
		field_input("ac1").type("2");
		panel()
			.find(".es-combobox__list [role='option'][data-highlighted]")
			.should("contain", "Option 2");
		search().type("{enter}");
		panel().should("not.exist");
		cy.get("@dialog").then((dialog) => expect(dialog.get_value("ac1")).to.eq("Option 2"));
	});

	it("maps a label to its value", () => {
		make_dialog("ac2", [
			{ label: "Option 1", value: "option_1" },
			{ label: "Option 2", value: "option_2" },
		]).as("dialog");
		field_input("ac2").type("2");
		search().type("{enter}");
		cy.get("@dialog").then((dialog) => {
			expect(dialog.get_value("ac2")).to.eq("option_2");
			expect(dialog.get_field("ac2").$input.val()).to.eq("Option 2");
		});
	});

	it("drops text that matches nothing when the list is the rule", () => {
		make_dialog("ac3", ["Option 1", "Option 2"]).as("dialog");
		field_input("ac3").type("2");
		search().type("{enter}");
		field_input("ac3").type("zzz");
		panel().find(".es-menu__empty").should("exist");
		panel().find(".es-combobox__footer").should("not.be.visible");
		cy.get(".modal-title").click();
		panel().should("not.exist");
		cy.get("@dialog").then((dialog) => expect(dialog.get_value("ac3")).to.eq("Option 2"));
	});

	it("offers typed text as a value when free text is allowed", () => {
		make_dialog("ac4", ["Option 1", "Option 2"], { ignore_validation: 1 }).as("dialog");
		field_input("ac4").type("Custom");
		panel().find(".es-combobox__footer [role='option']").should("contain", 'Use "Custom"');
		search().type("{enter}");
		panel().should("not.exist");
		cy.get("@dialog").then((dialog) => expect(dialog.get_value("ac4")).to.eq("Custom"));
		field_input("ac4").type("Other");
		cy.get(".modal-title").click();
		cy.get("@dialog").then((dialog) => expect(dialog.get_value("ac4")).to.eq("Other"));
	});

	it("opens with the search focused as a dialog's first field, and Enter after a pick runs the primary action", () => {
		cy.window().its("frappe.sys_defaults").should("exist");
		cy.window().then((win) => {
			win.__picked = null;
			const dialog = new win.frappe.ui.Dialog({
				title: "Jump",
				fields: [
					{
						label: "Field",
						fieldname: "ac6",
						fieldtype: "Autocomplete",
						options: ["Alpha", "Beta"],
						reqd: 1,
					},
				],
				primary_action_label: "Go",
				primary_action: ({ ac6 }) => {
					win.__picked = ac6;
					dialog.hide();
				},
				animate: false,
			});
			dialog.show();
		});
		cy.window().its("cur_dialog.display").should("eq", true);
		panel().should("exist");
		cy.focused().should("have.class", "es-combobox__input");
		// click first: Cypress drops the caret of an input focused by script
		search().click().type("Bet{enter}");
		panel().should("not.exist");
		cy.focused().should("have.class", "es-combobox__value");
		cy.focused().type("{enter}");
		cy.window().its("__picked").should("eq", "Beta");
		cy.get(".modal:visible").should("not.exist");
	});

	it("fires a native change on a pick", () => {
		make_dialog("ac7", ["Alpha", "Beta"]).as("dialog");
		cy.get("@dialog").then((dialog) => {
			dialog.__changed = 0;
			dialog.get_input("ac7").on("change", () => dialog.__changed++);
		});
		field_input("ac7").type("Bet");
		search().type("{enter}");
		cy.get("@dialog").its("__changed").should("eq", 1);
		cy.get("@dialog").then((dialog) => expect(dialog.get_value("ac7")).to.eq("Beta"));
	});

	it("uses get_query for the rows even when options are set", () => {
		make_dialog("ac8", ["Alpha", "Beta"], {
			get_query: () => ({
				query: "frappe.client.get_list",
				params: {
					doctype: "Role",
					fields: ["name as value", "name as label"],
					filters: { name: "System Manager" },
				},
			}),
		}).as("dialog");
		field_input("ac8").type("sys");
		panel().find(".es-combobox__list [role='option']").should("contain", "System Manager");
		panel().find(".es-combobox__list [role='option']").should("not.contain", "Alpha");
		search().type("{enter}");
		cy.get("@dialog").should((dialog) =>
			expect(dialog.get_value("ac8")).to.eq("System Manager")
		);
	});

	it("takes a new list from set_data", () => {
		make_dialog("ac5", ["Old 1", "Old 2"]).as("dialog");
		cy.get("@dialog").then((dialog) => dialog.get_field("ac5").set_data(["New 1", "New 2"]));
		field_input("ac5").focus();
		panel()
			.find(".es-combobox__list [role='option']")
			.should("have.length", 2)
			.first()
			.should("contain", "New 1");
		search().type("{esc}");
	});
});
