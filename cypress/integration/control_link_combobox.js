// The Link field with the combobox setting on: control_link.js scenarios,
// driven through the combobox panel. The setting is turned off again after.

context("Control Link (combobox)", () => {
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
		cy.create_records({
			doctype: "ToDo",
			description: "this is a test todo for link",
		}).as("todos");
	});

	function get_dialog_with_link() {
		// a control made before boot stays classic: wait for the boot data
		cy.window().its("frappe.sys_defaults").should("exist");
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
				// wait for the modal to be shown, else Bootstrap pulls focus out of the panel
				cy.window().its("cur_dialog.display").should("eq", true);
				return cy.wrap(dialog, { log: false });
			});
	}

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
		// let the pick's validation settle, or the next change is dropped
		cy.wait("@validate_link");
		cy.get("@dialog").then((dialog) => {
			cy.get("@todos").then((todos) => expect(dialog.get_value("link")).to.eq(todos[0]));
		});

		field_input().focus().type("{backspace}");
		field_input().should("have.value", "");
		panel().should("be.visible");
		search().type("{esc}");
		panel().should("not.exist");
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
			field_input().focus();
			cy.get(".frappe-control[data-fieldname=link] .btn-open")
				.should("be.visible")
				.should("have.attr", "href", `/desk/todo/${todos[0]}`);
			field_input().type("{ctrl}{enter}");
			cy.location("pathname").should("eq", `/desk/todo/${todos[0]}`);
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

		// keep the setter on: a worker holding stale ToDo meta answers with bare names
		cy.call("frappe.client.get_value", {
			doctype: "Property Setter",
			filters: { doc_type: "ToDo", property: "show_title_field_in_link" },
			fieldname: "value",
		}).then((r) => {
			if (r.message.value !== "1") {
				cy.call("frappe.client.set_value", {
					doctype: "Property Setter",
					name: "ToDo-main-show_title_field_in_link",
					fieldname: "value",
					value: "1",
				});
			}
		});

		// clear cached ToDo meta on every worker
		cy.call("frappe.sessions.clear");

		cy.reload();

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
		// the title is looked up after the pick lands: wait for it to show
		field_input().should("have.value", "this is a test todo for link");
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
			cy.reload();
			cy.intercept("/api/method/frappe.client.validate_link_and_fetch*").as("validate_link");
			// custom fields can push the field below the fold, where Cypress counts it hidden
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

			cy.get_field("assigned_by").type("invalid input", { delay: 100 });
			cy.get(".es-combobox__panel[data-state='open'] .es-menu__empty").should("exist");
			cy.get(".page-title").click();
			cy.wait("@validate_link");
			cy.window().its("cur_frm.doc.assigned_by").should("eq", undefined);
			cy.get(".frappe-control[data-fieldname=assigned_by_full_name] .control-value").should(
				"contain",
				""
			);

			cy.fill_field("assigned_by", cy.config("testUser"), "Link");
			cy.wait("@validate_link");
			cy.window().its("cur_frm.doc.assigned_by").should("eq", cy.config("testUser"));

			cy.get(".frappe-control[data-fieldname=assigned_by] [data-role='clear']").click({
				force: true,
			});
			cy.get(".es-combobox__panel[data-state='open'] .es-combobox__input").type("{esc}");
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
				panel()
					.find(".es-combobox__footer [role='option']")
					.should("contain", "Custom Link Option");
			});
	});

	describe("in a child table", () => {
		before(() => {
			cy.visit("/desk/website");
			cy.window()
				.its("frappe")
				.then((frappe) =>
					frappe.xcall("frappe.tests.ui_test_helpers.create_child_doctype", {
						name: "Child Test Link Combobox",
						fields: [
							{
								label: "Todo",
								fieldname: "todo",
								fieldtype: "Link",
								options: "ToDo",
								in_list_view: 1,
							},
							{
								label: "Note",
								fieldname: "note",
								fieldtype: "Data",
								in_list_view: 1,
							},
						],
					})
				)
				.then((frappe) =>
					frappe.xcall("frappe.tests.ui_test_helpers.create_doctype", {
						name: "Test Link Combobox Grid",
						fields: [
							{
								label: "Items",
								fieldname: "items",
								fieldtype: "Table",
								options: "Child Test Link Combobox",
							},
						],
					})
				);
		});

		it("opens on a cell click with the search focused; keys and the × clear", () => {
			cy.new_form("Test Link Combobox Grid");
			cy.get("@todos").then((todos) => {
				cy.window()
					.its("cur_frm")
					.then((frm) => {
						frm.add_child("items", { todo: todos[0] });
						frm.refresh_field("items");
					});

				cy.get(
					'.frappe-control[data-fieldname="items"] .grid-body .grid-row [data-fieldname="todo"] .static-area'
				)
					.should("contain", todos[0])
					.click();
				panel().should("be.visible");
				search().should("have.focus");

				search().type("{esc}");
				panel().should("not.exist");
				cy.get('.editable-row [data-fieldname="todo"] .es-combobox input')
					.as("cell")
					.should("have.focus");
				cy.window().its("cur_frm.doc.items.0.todo").should("eq", todos[0]);

				cy.get("@cell").type("{backspace}");
				panel().should("be.visible");
				cy.window().its("cur_frm.doc.items.0.todo").should("eq", todos[0]);
				search().type("{esc}");
				cy.window().its("cur_frm.doc.items.0.todo").should("eq", "");
				cy.get("@cell").should("have.value", "");

				cy.window().then((win) => {
					const row = win.cur_frm.doc.items[0];
					return win.frappe.model.set_value(row.doctype, row.name, "todo", todos[0]);
				});
				cy.get("@cell").invoke("val").should("not.be.empty");
				cy.get('.editable-row [data-fieldname="todo"] [data-role="clear"]').click({
					force: true,
				});
				cy.get("@cell").should("have.value", "");
				panel().should("be.visible");
				search().type("{esc}");
				cy.window().its("cur_frm.doc.items.0.todo").should("eq", "");
			});
		});

		it("keeps keyboard row navigation and tab-through data entry", () => {
			cy.new_form("Test Link Combobox Grid");
			cy.get("@todos").then((todos) => {
				cy.window()
					.its("cur_frm")
					.then((frm) => {
						frm.add_child("items", { todo: todos[0], note: "one" });
						frm.add_child("items", { todo: todos[0], note: "two" });
						frm.refresh_field("items");
					});
				const cell = (idx) =>
					`.frappe-control[data-fieldname="items"] .grid-body .grid-row[data-idx="${idx}"] [data-fieldname="todo"]`;

				cy.get(`${cell(1)} .static-area`).click();
				panel().should("be.visible");
				search().type("{esc}");
				panel().should("not.exist");
				cy.get(`${cell(1)} .es-combobox input`).should("have.focus");
				cy.realPress("ArrowDown");
				cy.window().its("frappe.ui.form.editable_row.doc.idx").should("eq", 2);
				cy.get(`${cell(2)} .es-combobox input`).should("have.focus");
				panel().should("not.exist");

				cy.realPress(["Alt", "ArrowDown"]);
				panel().should("be.visible");
				search().should("have.focus");
				cy.window().its("frappe.ui.form.editable_row.doc.idx").should("eq", 2);
				cy.window().its("cur_frm.doc.items.1.todo").should("eq", todos[0]);
				search().type("{esc}");
				panel().should("not.exist");
				cy.get(`${cell(2)} .es-combobox input`).should("have.focus");

				cy.realPress("Tab");
				cy.get('.editable-row [data-fieldname="note"] input').should("have.focus");
				cy.realPress(["Shift", "Tab"]);
				cy.get(`${cell(2)} .es-combobox input`).should("have.focus");
				panel().should("not.exist");

				cy.get('.frappe-control[data-fieldname="items"] .grid-add-row').click();
				panel().should("be.visible");
				search().type("todo for link", { delay: 100 });
				panel()
					.find(".es-combobox__list [role='option'][data-highlighted]")
					.should("contain", todos[0]);
				cy.realPress("Tab");
				panel().should("not.exist");
				cy.window().its("cur_frm.doc.items.2.todo").should("eq", todos[0]);
				cy.get('.editable-row [data-fieldname="note"] input').should("have.focus");
			});
		});
	});

	it("pages a long list on scroll, translated doctypes included", () => {
		cy.window().its("frappe.sys_defaults").should("exist");
		cy.dialog({
			title: "Link",
			fields: [{ label: "DocType", fieldname: "dt", fieldtype: "Link", options: "DocType" }],
		}).as("dialog");
		cy.window().its("cur_dialog.display").should("eq", true);
		cy.get(".frappe-control[data-fieldname=dt] .es-combobox input").focus();
		panel().should("be.visible");
		panel().find(".es-combobox__list [role='option']").should("have.length", 10);
		panel().find(".es-combobox__list").scrollTo("bottom");
		panel().find(".es-combobox__list [role='option']").should("have.length.gt", 10);
		search().type("{esc}");
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
