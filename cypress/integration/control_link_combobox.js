// The Link field with the combobox setting on: control_link.js scenarios,
// driven through the combobox panel. The setting is turned off again after.

context("Control Link (combobox)", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		// the × button follows the second setting
		cy.set_value("System Settings", "System Settings", {
			enable_combobox_link_field: 1,
			allow_clearing_link_fields: 1,
		});
	});

	after(() => {
		cy.visit("/desk/website");
		cy.set_value("System Settings", "System Settings", {
			enable_combobox_link_field: 0,
			allow_clearing_link_fields: 0,
		});
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

	// scoped to the live modal: a hidden dialog keeps its own copy of the field
	const field_input = () =>
		cy.get(".modal:visible .frappe-control[data-fieldname=link] .es-combobox input");
	const panel = () => cy.get(".es-combobox__panel[data-state='open']");
	const search = () => panel().find(".es-combobox__input");
	// a hidden dialog keeps its markup, so clicks and panels stay scoped to the live one
	const click_away = () => cy.get(".modal:visible .modal-title").click();
	const close_dialog = () => {
		cy.window().then((win) => win.cur_dialog && win.cur_dialog.hide());
		cy.get(".modal:visible").should("not.exist");
	};
	// a paste arrives as a beforeinput carrying a dataTransfer
	const paste = (text) =>
		field_input().then(($input) => {
			const data = new DataTransfer();
			data.setData("text/plain", text);
			$input[0].dispatchEvent(
				new InputEvent("beforeinput", {
					inputType: "insertFromPaste",
					dataTransfer: data,
					bubbles: true,
					cancelable: true,
				})
			);
		});

	it("picks a listed row, drops text that matches nothing, and opens the record", () => {
		get_dialog_with_link().as("dialog");
		cy.get("@dialog").then((dialog) => {
			const field = dialog.get_field("link");
			expect(field.combobox).to.exist;
			expect(field.$input.closest(".es-combobox").length).to.eq(1);
		});

		// text matching nothing leaves the field empty
		field_input().type("invalid value", { delay: 100 });
		panel().find(".es-menu__empty").should("contain", "invalid value");
		click_away();
		panel().should("not.exist");
		field_input().should("have.value", "");
		cy.get("@dialog").then((dialog) => expect(dialog.get_value("link")).to.equal(""));

		cy.get("@todos").then((todos) => {
			// Enter picks the highlighted row
			field_input().type("todo for link", { delay: 100 });
			panel()
				.find(".es-combobox__list [role='option'][data-highlighted]")
				.should("contain", todos[0]);
			search().type("{enter}");
			panel().should("not.exist");
			cy.get("@dialog").should((dialog) => expect(dialog.get_value("link")).to.eq(todos[0]));

			// a partial query left behind keeps the value
			field_input().type("zzz", { delay: 100 });
			panel().find(".es-menu__empty").should("exist");
			click_away();
			panel().should("not.exist");
			cy.get("@dialog").should((dialog) => expect(dialog.get_value("link")).to.eq(todos[0]));

			// the open-link button, and Ctrl+Enter as its shortcut
			field_input().focus();
			cy.get(".frappe-control[data-fieldname=link] .btn-open")
				.should("be.visible")
				.should("have.attr", "href", `/desk/todo/${todos[0]}`);
			field_input().type("{ctrl}{enter}");
			cy.location("pathname").should("eq", `/desk/todo/${todos[0]}`);
		});
	});

	it("commits text typed or pasted at close, even before the rows arrive", () => {
		cy.get("@todos").then((todos) => {
			get_dialog_with_link().as("dialog");

			// the full name of a listed row is committed by clicking away
			field_input().type(todos[0], { delay: 100 });
			panel().find(".es-combobox__list [role='option']").should("contain", todos[0]);
			click_away();
			panel().should("not.exist");
			cy.get("@dialog").should((dialog) => expect(dialog.get_value("link")).to.eq(todos[0]));
			close_dialog();

			// a paste opens the panel with the first line as the query
			get_dialog_with_link().as("pasted");
			search().type("{esc}");
			panel().should("not.exist");
			paste("pasted name\nsecond line");
			panel().should("be.visible");
			search().should("have.value", "pasted name");
			search().type("{esc}");
			panel().should("not.exist");

			// pasted and tabbed away at once: the row is looked up and committed
			paste(todos[0]);
			panel().should("be.visible");
			cy.realPress("Tab");
			panel().should("not.exist");
			// the looked-up row, not just the text: the widget holds the value
			cy.get("@pasted").should((dialog) =>
				expect(dialog.get_field("link").combobox.get_value()).to.eq(todos[0])
			);
			cy.get("@pasted").should((dialog) => expect(dialog.get_value("link")).to.eq(todos[0]));
			close_dialog();

			// with ignore_link_validation any text is a value
			cy.dialog({
				title: "Link",
				fields: [
					{
						label: "Campaign",
						fieldname: "campaign",
						fieldtype: "Link",
						options: "ToDo",
						ignore_link_validation: 1,
					},
				],
			}).as("free");
			cy.get(".frappe-control[data-fieldname=campaign] .es-combobox input").type(
				"summer-sale"
			);
			panel().find(".es-menu__empty").should("exist");
			click_away();
			panel().should("not.exist");
			cy.get("@free").should((dialog) =>
				expect(dialog.get_value("campaign")).to.eq("summer-sale")
			);
		});
	});

	it("clears a value, and settles a clear typed back or replaced", () => {
		cy.get("@todos").then((todos) => {
			get_dialog_with_link().as("dialog");
			cy.intercept("/api/method/frappe.client.validate_link_and_fetch*").as("validate_link");
			field_input().type("todo for link", { delay: 100 });
			search().type("{enter}");
			panel().should("not.exist");
			// let the pick's validation settle, or the next change is dropped
			cy.wait("@validate_link");
			cy.get("@dialog").should((dialog) => expect(dialog.get_value("link")).to.eq(todos[0]));

			// cleared and typed back before clicking away: the value stands
			field_input().focus().type("{backspace}");
			panel().should("be.visible");
			search().type(todos[0]);
			panel().find(".es-combobox__list [role='option']").should("contain", todos[0]);
			click_away();
			panel().should("not.exist");
			cy.get("@dialog").should((dialog) => expect(dialog.get_value("link")).to.eq(todos[0]));
			field_input().invoke("val").should("not.be.empty");

			// a script's set_value while the panel is up wins over the pending clear
			field_input().focus().type("{backspace}");
			panel().should("be.visible");
			panel().find(".es-combobox__list [role='option']").should("have.length.gt", 1);
			cy.window().then((win) => {
				const rows = win.cur_dialog.get_field("link").combobox.rows;
				const other = rows.map((r) => r.option.value).find((v) => v !== todos[0]);
				cy.get("@dialog").then((dialog) => dialog.set_value("link", other));
				search().type("{esc}");
				panel().should("not.exist");
				cy.get("@dialog").should((dialog) =>
					expect(dialog.get_value("link")).to.eq(other)
				);
				field_input().invoke("val").should("not.be.empty");
			});

			// and an empty value can be set explicitly
			field_input().focus().type("{backspace}");
			field_input().should("have.value", "");
			panel().should("be.visible");
			search().type("{esc}");
			panel().should("not.exist");
			cy.get("@dialog").should((dialog) => expect(dialog.get_value("link")).to.equal(""));
		});
	});

	it("is driven from the keyboard: arrows open the panel, move through it and pick", () => {
		get_dialog_with_link().as("dialog");
		panel().find(".es-combobox__list [role='option']").should("have.length.gt", 1);
		cy.realPress("ArrowDown");
		cy.window().then((win) => {
			const field = win.cur_dialog.get_field("link");
			const moved_to = field.combobox.highlighted.option.value;
			cy.realPress("Tab");
			panel().should("not.exist");
			cy.get("@dialog").should((dialog) => expect(dialog.get_value("link")).to.eq(moved_to));
		});

		// ArrowDown reopens it, Escape closes it and hands focus back
		field_input().focus().type("{downArrow}");
		panel().should("be.visible");
		search().should("have.focus");
		search().type("{esc}");
		panel().should("not.exist");
		field_input().should("have.focus");
	});

	it("Select mode lists everything, jumps by letter, and falls back to Search when too long", () => {
		cy.window().its("frappe.sys_defaults").should("exist");
		cy.window().then((win) => {
			win.frappe.boot.link_settings = {
				...(win.frappe.boot.link_settings || {}),
				Role: { display_mode: "Select" },
				DocType: { display_mode: "Select" },
			};
		});

		// a short list: no search box, and the first letters jump to a row
		cy.dialog({
			title: "Link",
			fields: [{ label: "Role", fieldname: "role", fieldtype: "Link", options: "Role" }],
		}).as("dialog");
		panel().find(".es-combobox__input").should("not.exist");
		panel().type("{esc}");
		panel().should("not.exist");
		cy.get(".frappe-control[data-fieldname=role] .es-combobox input").type("sys");
		panel().find("[role='option'][data-highlighted]").should("contain", "System Manager");
		cy.realPress("Tab");
		panel().should("not.exist");
		cy.get("@dialog").should((dialog) =>
			expect(dialog.get_value("role")).to.eq("System Manager")
		);
		close_dialog();

		// too many rows to preload: the panel reopens as a search, and stays one
		cy.dialog({
			title: "Link",
			fields: [{ label: "DocType", fieldname: "dt", fieldtype: "Link", options: "DocType" }],
		}).as("dt");
		panel().find(".es-combobox__input").should("exist");
		panel().find(".es-combobox__list [role='option']").should("have.length", 10);
		search().type("{esc}");
		panel().should("not.exist");
		cy.get(".frappe-control[data-fieldname=dt] .es-combobox input").focus();
		panel().find(".es-combobox__input").should("exist");
		panel().find(".es-combobox__list [role='option']").should("have.length", 10);
		search().type("{esc}");
	});

	it("pages a long list on scroll, and map_options and link_options extend the rows", () => {
		cy.window().its("frappe.sys_defaults").should("exist");
		cy.dialog({
			title: "Link",
			fields: [{ label: "DocType", fieldname: "dt", fieldtype: "Link", options: "DocType" }],
		}).as("dialog");
		cy.window().its("cur_dialog.display").should("eq", true);

		// a page at a time, with the next one fetched on scroll (DocType is translated)
		cy.get(".frappe-control[data-fieldname=dt] .es-combobox input").focus();
		panel().should("be.visible");
		panel().find(".es-combobox__list [role='option']").should("have.length", 10);
		panel().find(".es-combobox__list").scrollTo("bottom");
		panel().find(".es-combobox__list [role='option']").should("have.length.gt", 10);
		search().type("{esc}");
		panel().should("not.exist");

		// every page returns both groups: later rows join the group with that label
		cy.get("@dialog").then((dialog) => {
			dialog.get_field("dt").map_options = (rows) => [
				{ group: "Recently used", options: [rows[0]] },
				{ group: "All", options: rows },
			];
		});
		cy.get(".frappe-control[data-fieldname=dt] .es-combobox input").focus();
		panel().find(".es-menu__group-label").should("have.length", 2);
		panel().find(".es-menu__group-label").first().should("contain", "Recently used");
		panel().find(".es-combobox__list").scrollTo("bottom");
		panel().find(".es-combobox__list [role='option']").should("have.length.gt", 11);
		// page 2 continued the "All" group instead of adding a header
		panel().find(".es-menu__group-label").should("have.length", 2);
		search().type("{esc}");
		close_dialog();

		// link_options adds rows of an app's own under the list
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

				get_dialog_with_link().as("custom");
				panel().should("be.visible");
				search().type("custom", { delay: 100 });
				panel()
					.find(".es-combobox__footer [role='option']")
					.should("contain", "Custom Link Option");
			});
	});

	it("shows a link title in the field and in the rows", () => {
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

	it("updates dependent fields on a form, and clears them with the value", () => {
		cy.get("@todos").then((todos) => {
			// a site default for the field would make the pick below a no-op
			cy.set_value("ToDo", todos[0], { assigned_by: "" });
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

			// a partial query left behind keeps the value and its fetched fields
			cy.get_field("assigned_by").type("invalid input", { delay: 100 });
			cy.get(".es-combobox__panel[data-state='open'] .es-menu__empty").should("exist");
			cy.get(".page-title").click();
			cy.get(".es-combobox__panel[data-state='open']").should("not.exist");
			cy.window().its("cur_frm.doc.assigned_by").should("eq", cy.config("testUser"));
			cy.get(".frappe-control[data-fieldname=assigned_by_full_name] .control-value").should(
				"not.be.empty"
			);

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

		it("opens in a cell, clears, keeps row navigation and tabs through the row", () => {
			// a cell click opens the panel with its search focused; keys and the × clear
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

			// row navigation and tab-through data entry
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

			// Tab from a link in the last column still adds the next row
			cy.new_form("Test Link Combobox Grid");
			cy.get("@todos").then((todos) => {
				cy.window()
					.its("cur_frm")
					.then((frm) => {
						const grid = frm.fields_dict.items.grid;
						grid.docfields.find((df) => df.fieldname === "note").in_list_view = 0;
						grid.reset_grid();
					});
				cy.get('.frappe-control[data-fieldname="items"] .grid-add-row').click();
				panel().should("be.visible");
				search().type("todo for link", { delay: 100 });
				panel()
					.find(".es-combobox__list [role='option'][data-highlighted]")
					.should("contain", todos[0]);
				cy.realPress("Tab");
				panel().should("not.exist");
				cy.window().its("cur_frm.doc.items.0.todo").should("eq", todos[0]);
				cy.window().its("cur_frm.doc.items.length").should("eq", 2);
				cy.window().its("frappe.ui.form.editable_row.doc.idx").should("eq", 2);
			});
		});
	});
});
