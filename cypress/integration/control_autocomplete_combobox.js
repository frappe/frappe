// The Autocomplete field with the combobox setting on: control_autocomplete.js
// scenarios through the combobox panel, plus free text and set_data.

context("Control Autocomplete (combobox)", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.set_value("System Settings", "System Settings", { enable_combobox_link_field: 1 });
	});

	after(() => {
		cy.visit("/desk/website");
		cy.set_value("System Settings", "System Settings", { enable_combobox_link_field: 0 });
	});

	beforeEach(() => {
		cy.visit("/desk/website");
	});

	const make_dialog = (fieldname, options, extra = {}) => {
		cy.window().its("frappe.sys_defaults").should("exist");
		return cy.dialog({
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
	};
	const field_input = (fieldname) =>
		cy.get(`.frappe-control[data-fieldname=${fieldname}] .es-combobox input`);
	const panel = () => cy.get(".es-combobox__panel[data-state='open']");
	const search = () => panel().find(".es-combobox__input");
	// one dialog at a time: a stale panel would answer the shared selectors
	const close_dialog = () => {
		cy.window().then((win) => win.cur_dialog && win.cur_dialog.hide());
		cy.get(".modal.show").should("not.exist");
	};

	it("picks a typed match, maps its label to a value, and fires one native change", () => {
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
		close_dialog();

		// a {label, value} list stores the value and shows the label
		make_dialog("ac2", [
			{ label: "Option 1", value: "option_1" },
			{ label: "Option 2", value: "option_2" },
		]).as("mapped");
		field_input("ac2").type("2");
		search().type("{enter}");
		cy.get("@mapped").then((dialog) => {
			expect(dialog.get_value("ac2")).to.eq("option_2");
			expect(dialog.get_field("ac2").$input.val()).to.eq("Option 2");
		});
		close_dialog();

		// the pick reaches .on("change") listeners exactly once
		make_dialog("ac7", ["Alpha", "Beta"]).as("changed");
		cy.get("@changed").then((dialog) => {
			dialog.__changed = 0;
			dialog.get_input("ac7").on("change", () => dialog.__changed++);
		});
		field_input("ac7").type("Bet");
		search().type("{enter}");
		cy.get("@changed").its("__changed").should("eq", 1);
		cy.get("@changed").then((dialog) => expect(dialog.get_value("ac7")).to.eq("Beta"));
	});

	it("keeps free text when it is allowed, and drops it when the list is the rule", () => {
		// no free text: text matching nothing leaves the value alone
		make_dialog("ac3", ["Option 1", "Option 2"]).as("dialog");
		field_input("ac3").type("2");
		search().type("{enter}");
		field_input("ac3").type("zzz");
		panel().find(".es-menu__empty").should("exist");
		panel().find(".es-combobox__footer").should("not.be.visible");
		cy.get(".modal.show .modal-title").click();
		panel().should("not.exist");
		cy.get("@dialog").then((dialog) => expect(dialog.get_value("ac3")).to.eq("Option 2"));
		close_dialog();

		// free text: the footer row offers it, and a click away commits it
		make_dialog("ac4", ["Option 1", "Option 2"], { ignore_validation: 1 }).as("free");
		field_input("ac4").type("Custom");
		panel().find(".es-combobox__footer [role='option']").should("contain", 'Use "Custom"');
		search().type("{enter}");
		panel().should("not.exist");
		cy.get("@free").then((dialog) => expect(dialog.get_value("ac4")).to.eq("Custom"));
		field_input("ac4").type("Other");
		cy.get(".modal.show .modal-title").click();
		cy.get("@free").then((dialog) => expect(dialog.get_value("ac4")).to.eq("Other"));

		// Tab keeps the text, unless the arrow keys moved to a row
		field_input("ac4").type("Opt");
		search().type("{downArrow}");
		panel()
			.find(".es-combobox__list [role='option'][data-highlighted]")
			.should("contain", "Option 2");
		cy.realPress("Tab");
		panel().should("not.exist");
		cy.get("@free").then((dialog) => expect(dialog.get_value("ac4")).to.eq("Option 2"));
	});

	it("takes rows from get_query or set_data, and opens focused as a dialog's first field", () => {
		// a get_query method searches on the server, options or not
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
		close_dialog();

		// set_data replaces the list behind an open field
		make_dialog("ac5", ["Old 1", "Old 2"]).as("data");
		cy.get("@data").then((dialog) => dialog.get_field("ac5").set_data(["New 1", "New 2"]));
		field_input("ac5").focus();
		panel()
			.find(".es-combobox__list [role='option']")
			.should("have.length", 2)
			.first()
			.should("contain", "New 1");
		search().type("{esc}");
		close_dialog();

		// first field of a dialog: the panel's search takes focus, and Enter
		// after a pick runs the primary action
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
		cy.get(".modal.show").should("not.exist");
	});
});
