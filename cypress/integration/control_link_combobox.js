// The Link field with System Settings > "Enable Combobox Link Field" on:
// the same scenarios as control_link.js, driven through the combobox
// panel (search box inside, rows in <body>) instead of the classic
// dropdown next to the input. The per-browser override in localStorage
// turns the control on for this spec without touching the site setting.

context("Control Link (combobox)", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
	});

	beforeEach(() => {
		cy.visit("/desk/website");
		cy.window().then((win) => win.localStorage.setItem("combobox_link_field", "1"));
		cy.create_records({
			doctype: "ToDo",
			description: "this is a test todo for link",
		}).as("todos");
	});

	afterEach(() => {
		cy.window().then((win) => win.localStorage.removeItem("combobox_link_field"));
	});

	function get_dialog_with_link() {
		return cy
			.dialog({
				title: "Link",
				fields: [
					{
						label: "Select ToDo",
						fieldname: "link",
						fieldtype: "Link",
						options: "ToDo",
					},
				],
			})
			.then((dialog) => {
				// cy.dialog returns before the modal has faded in, and until
				// its shown handler runs Bootstrap pulls focus back into the
				// modal from anything outside it (the panel lives in <body>):
				// type only once the dialog is shown, as a user would
				cy.window().its("cur_dialog.display").should("eq", true);
				return cy.wrap(dialog, { log: false });
			});
	}

	// the field's own input (inside the trigger), the open panel, its search box
	const field_input = () => cy.get(".frappe-control[data-fieldname=link] .es-combobox input");
	const panel = () => cy.get(".es-combobox__panel[data-state='open']");
	const search = () => panel().find(".es-combobox__input");

	it("is the combobox control", () => {
		get_dialog_with_link().as("dialog");
		cy.get("@dialog").then((dialog) => {
			const field = dialog.get_field("link");
			expect(field.combobox).to.exist;
			expect(field.$input.closest(".es-combobox").length).to.eq(1);
		});
	});

	it("should set the valid value", () => {
		get_dialog_with_link().as("dialog");

		cy.insert_doc(
			"Property Setter",
			{
				doctype: "Property Setter",
				doc_type: "ToDo",
				property: "show_title_field_in_link",
				property_type: "Check",
				doctype_or_field: "DocType",
				value: "0",
			},
			true
		);

		// typing on the field opens the panel with the text as the query
		field_input().type("todo for link", { delay: 100 });
		panel().should("be.visible");
		cy.get("@todos").then((todos) => {
			panel()
				.find(".es-combobox__list [role='option'][data-highlighted]")
				.should("contain", todos[0]);
		});
		search().type("{enter}");
		panel().should("not.exist");
		cy.get("@dialog").then((dialog) => {
			cy.get("@todos").then((todos) => {
				expect(dialog.get_value("link")).to.eq(todos[0]);
			});
		});
	});

	it("should unset invalid value", () => {
		get_dialog_with_link().as("dialog");

		cy.intercept("/api/method/frappe.client.validate_link_and_fetch*").as("validate_link");
		field_input().type("invalid value", { delay: 100 });
		panel().find(".es-menu__empty").should("contain", "invalid value");
		// clicking away leaves the typed text behind: it is validated like the
		// classic blur, and an unknown name is unset
		cy.get(".modal-title").click();
		cy.wait("@validate_link");
		field_input().should("have.value", "");
		cy.get("@dialog").then((dialog) => {
			expect(dialog.get_value("link")).to.equal("");
		});
	});

	it("should be possible set empty value explicitly", () => {
		get_dialog_with_link().as("dialog");

		cy.intercept("/api/method/frappe.client.validate_link_and_fetch*").as("validate_link");
		field_input().type("todo for link", { delay: 100 });
		search().type("{enter}");
		panel().should("not.exist");
		// a change while the pick is still being validated is dropped (the
		// control is inside its change event), so let the pick settle first
		cy.wait("@validate_link");
		cy.get("@dialog").then((dialog) => {
			cy.get("@todos").then((todos) => expect(dialog.get_value("link")).to.eq(todos[0]));
		});

		// Backspace on the field clears it (the × button is hover-only)
		field_input().focus().type("{backspace}");
		field_input().should("have.value", "");
		cy.get("@dialog").then((dialog) => {
			expect(dialog.get_value("link")).to.equal("");
		});
	});

	it("should show open link button", () => {
		get_dialog_with_link().as("dialog");

		cy.get("@todos").then((todos) => {
			field_input().type(todos[0], { delay: 100 });
			search().type("{enter}");
			panel().should("not.exist");
			// the open arrow is a link, shown while the field has focus
			field_input().focus();
			cy.get(".frappe-control[data-fieldname=link] .btn-open")
				.should("be.visible")
				.should("have.attr", "href", `/desk/todo/${todos[0]}`);
		});
	});

	it("show title field in link", () => {
		cy.insert_doc(
			"Property Setter",
			{
				doctype: "Property Setter",
				doc_type: "ToDo",
				property: "show_title_field_in_link",
				property_type: "Check",
				doctype_or_field: "DocType",
				value: "1",
			},
			true
		);

		cy.reload();
		cy.window().then((win) => win.localStorage.setItem("combobox_link_field", "1"));

		get_dialog_with_link().as("dialog");
		cy.window()
			.its("frappe")
			.then((frappe) => {
				frappe.boot.link_title_doctypes = ["ToDo"];
			});

		field_input().type("todo for link", { delay: 100 });
		panel()
			.find(".es-combobox__list [role='option'][data-highlighted]")
			.should("contain", "this is a test todo for link");
		search().type("{enter}");
		panel().should("not.exist");
		cy.get("@dialog").then((dialog) => {
			cy.get("@todos").then((todos) => {
				const field = dialog.get_field("link");
				expect(field.get_value()).to.eq(todos[0]);
				expect(field.get_label_value()).to.eq("this is a test todo for link");
			});
		});
	});

	it("should update dependant fields (via fetch_from)", () => {
		cy.get("@todos").then((todos) => {
			cy.visit(`/desk/todo/${todos[0]}`);
			cy.window().then((win) => win.localStorage.setItem("combobox_link_field", "1"));
			cy.reload();
			cy.intercept("/api/method/frappe.client.validate_link_and_fetch*").as("validate_link");
			// custom fields on a site can push the field below the fold, where
			// Cypress counts it as hidden
			cy.get(".frappe-control[data-fieldname=assigned_by]").scrollIntoView();

			cy.fill_field("assigned_by", cy.config("testUser"), "Link");
			cy.wait("@validate_link");
			cy.call("frappe.client.get_value", {
				doctype: "User",
				filters: { name: cy.config("testUser") },
				fieldname: "full_name",
			}).then((r) => {
				cy.get(
					".frappe-control[data-fieldname=assigned_by_full_name] .control-value"
				).should("contain", r.message.full_name);
			});
			cy.window().its("cur_frm.doc.assigned_by").should("eq", cy.config("testUser"));

			// an unknown name left behind by clicking away is validated and unset
			cy.get_field("assigned_by").type("invalid input", { delay: 100 });
			cy.get(".es-combobox__panel[data-state='open'] .es-menu__empty").should("exist");
			cy.get(".page-title").click();
			cy.wait("@validate_link");
			cy.window().its("cur_frm.doc.assigned_by").should("eq", undefined);
			cy.get(".frappe-control[data-fieldname=assigned_by_full_name] .control-value").should(
				"contain",
				""
			);

			// set a valid value again
			cy.fill_field("assigned_by", cy.config("testUser"), "Link");
			cy.wait("@validate_link");
			cy.window().its("cur_frm.doc.assigned_by").should("eq", cy.config("testUser"));

			// clear with the keyboard
			cy.get_field("assigned_by").focus().type("{backspace}");
			cy.window().its("cur_frm.doc.assigned_by").should("eq", "");
			cy.get(".frappe-control[data-fieldname=assigned_by_full_name] .control-value").should(
				"contain",
				""
			);
		});
	});

	it("show custom link option", () => {
		cy.window()
			.its("frappe")
			.then((frappe) => {
				frappe.ui.form.ControlLink.link_options = () => [
					{
						html: "<span class='text-primary custom-link-option'>Custom Link Option</span>",
						label: "Custom Link Option",
						value: "custom__link_option",
						action: () => {},
					},
				];

				get_dialog_with_link().as("dialog");
				field_input().type("custom", { delay: 100 });
				// custom rows sit in the footer, rendered as text
				panel()
					.find(".es-combobox__footer [role='option']")
					.should("contain", "Custom Link Option");
			});
	});

	it("keeps the panel keyboard-driven", () => {
		get_dialog_with_link().as("dialog");
		field_input().focus().type("{downArrow}");
		panel().should("be.visible");
		search().should("have.focus");
		search().type("{esc}");
		panel().should("not.exist");
		field_input().should("have.focus");
	});
});
