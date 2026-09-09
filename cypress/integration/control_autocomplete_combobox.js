// The Autocomplete field with System Settings > "Enable Combobox Link and
// Autocomplete Fields" on: the same scenarios as control_autocomplete.js,
// driven through the combobox panel, plus free text and set_data.

function set_combobox_setting(on) {
	cy.call("frappe.client.set_value", {
		doctype: "System Settings",
		name: "System Settings",
		fieldname: "enable_combobox_link_field",
		value: on ? 1 : 0,
	});
}

context("Control Autocomplete (combobox)", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		set_combobox_setting(true);
	});

	after(() => {
		cy.visit("/desk/website");
		set_combobox_setting(false);
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
		// the "Use" row is the only match, so Enter picks it
		panel().find(".es-combobox__footer [role='option']").should("contain", 'Use "Custom"');
		search().type("{enter}");
		panel().should("not.exist");
		cy.get("@dialog").then((dialog) => expect(dialog.get_value("ac4")).to.eq("Custom"));
		// clicking away commits typed text too
		field_input("ac4").type("Other");
		cy.get(".modal-title").click();
		cy.get("@dialog").then((dialog) => expect(dialog.get_value("ac4")).to.eq("Other"));
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
