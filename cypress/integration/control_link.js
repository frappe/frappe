context("Control Link", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
	});

	// The description of the ToDo this test made, and the part of it worth typing. Two tests below
	// find that record by typing into a Link field and then assert the field picked the record
	// they just made. `beforeEach` runs once per test and nothing deletes what it creates, so with
	// one fixed description the second such test is already searching against more than one match
	// and its assertion is a coin toss. Both were failing on exactly that.
	//
	// Only the stamp is typed, since the field searches the whole description and typing runs at
	// one character per 100ms.
	let todo_stamp;
	let todo_description;

	// The user `cy.login()` signs in as. Read from the config rather than from `frappe.user.name`
	// on the page: `cy.window()` resolves as soon as `frappe` exists, which can be before boot has
	// filled it in, and the name is `Guest` until then. Two tests below switch this user's
	// language, and one of them was intermittently switching Guest's instead, failing on a 403
	// and leaving the real user in German.
	const test_user = () => Cypress.config("testUser") || "Administrator";

	beforeEach(() => {
		cy.visit("/desk/website");
		todo_stamp = String(Date.now());
		todo_description = `this is a test todo for link ${todo_stamp}`;
		cy.create_records({
			doctype: "ToDo",
			description: todo_description,
		}).as("todos");
	});

	// One test here switches the logged-in user to German, and the test after it switches back.
	// That is not cleanup: it only runs if it runs. A failure in the German test, a spec filter,
	// or an interrupted run leaves the user in German for good, and every other spec that reads
	// English text off the screen then fails somewhere else entirely with no clue why. That is
	// how `routing.js`, `view_routing.js` and `awesome_bar.js` came to be failing on a bench
	// where nothing was wrong with them.
	//
	// `set_value` is a plain API call, so this holds even when the page never loaded.
	after(() => {
		cy.set_value("User", test_user(), { language: "en" });
	});

	function get_dialog_with_link() {
		return cy.dialog({
			title: "Link",
			fields: [
				{
					label: "Select ToDo",
					fieldname: "link",
					fieldtype: "Link",
					options: "ToDo",
				},
			],
		});
	}

	function get_dialog_with_gender_link() {
		let dialog = cy.dialog({
			title: "Link",
			fields: [
				{
					label: "Select Gender",
					fieldname: "link",
					fieldtype: "Link",
					options: "Gender",
				},
			],
		});
		cy.wait(500);
		return dialog;
	}

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

		cy.get(".frappe-control[data-fieldname=link] input").focus().as("input");
		// Wait for dropdown to appear (request might be cached)
		cy.get("@input").parent().findByRole("listbox").should("be.visible");
		cy.wait(200);
		cy.get("@input").type(todo_stamp, { delay: 100 });
		// Wait for dropdown to update with search results
		cy.wait(500);
		cy.get("@input").parent().findByRole("listbox").should("be.visible");
		cy.get("@input").type("{enter}");
		cy.get("@input").blur();
		cy.get("@dialog").then((dialog) => {
			cy.get("@todos").then((todos) => {
				let value = dialog.get_value("link");
				expect(value).to.eq(todos[0]);
			});
		});
	});

	it("should unset invalid value", () => {
		get_dialog_with_link().as("dialog");

		cy.intercept("/api/method/frappe.client.validate_link_and_fetch*").as("validate_link");
		cy.get(".frappe-control[data-fieldname=link] input").focus().as("input");
		// Wait for dropdown to appear (request might be cached)
		cy.get("@input").parent().findByRole("listbox").should("be.visible");
		cy.wait(200);
		cy.get("@input").type("invalid value", { delay: 100 }).blur();
		cy.wait("@validate_link");
		cy.get("@input").should("have.value", "");
	});

	it("should be possible set empty value explicitly", () => {
		get_dialog_with_link().as("dialog");

		cy.intercept("/api/method/frappe.client.validate_link_and_fetch*").as("validate_link");

		cy.get(".frappe-control[data-fieldname=link] input").focus().as("input");
		// Wait for dropdown to appear (request might be cached)
		cy.get("@input").parent().findByRole("listbox").should("be.visible");
		cy.wait(200);
		cy.get("@input").type("  ", { delay: 100 }).blur();
		cy.wait("@validate_link");
		cy.get("@input").should("have.value", "");
		cy.window()
			.its("cur_dialog")
			.then((dialog) => {
				expect(dialog.get_value("link")).to.equal("");
			});
	});

	it("should show open link button", () => {
		get_dialog_with_link().as("dialog");

		cy.get("@todos").then((todos) => {
			cy.get(".frappe-control[data-fieldname=link] input").focus().as("input");
			// Wait for dropdown to appear (request might be cached)
			cy.get("@input").parent().findByRole("listbox").should("be.visible");
			cy.wait(200);
			cy.get("@input").type(todos[0], { delay: 100 }).blur();
			// not waiting for validate_link because it will not get called
			cy.get("@input").trigger("mouseover");
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

		get_dialog_with_link().as("dialog");
		cy.window()
			.its("frappe")
			.then((frappe) => {
				if (!frappe.boot) {
					frappe.boot = {
						link_title_doctypes: ["ToDo"],
					};
				} else {
					frappe.boot.link_title_doctypes = ["ToDo"];
				}
			});

		cy.get(".frappe-control[data-fieldname=link] input").focus().as("input");
		// Wait for dropdown to appear (request might be cached)
		cy.get("@input").parent().findByRole("listbox").should("be.visible");
		cy.wait(200);
		cy.get("@input").type(todo_stamp, { delay: 100 });
		// Wait for dropdown to update with search results
		cy.wait(500);
		cy.get(".frappe-control[data-fieldname=link] ul").should("be.visible");
		cy.get("@input").type("{enter}");
		cy.get("@input").blur();
		cy.get("@dialog").then((dialog) => {
			cy.get("@todos").then((todos) => {
				let field = dialog.get_field("link");
				let value = field.get_value();
				let label = field.get_label_value();

				expect(value).to.eq(todos[0]);
				expect(label).to.eq(todo_description);
			});
		});
	});

	it("should update dependant fields (via fetch_from)", () => {
		cy.get("@todos").then((todos) => {
			cy.visit(`/desk/todo/${todos[0]}`);
			cy.intercept("/api/method/frappe.client.validate_link_and_fetch*").as("validate_link");

			cy.fill_field("assigned_by", cy.config("testUser"), "Link");
			cy.call("frappe.client.get_value", {
				doctype: "User",
				filters: {
					name: cy.config("testUser"),
				},
				fieldname: "full_name",
			}).then((r) => {
				cy.get(
					".frappe-control[data-fieldname=assigned_by_full_name] .control-value"
				).should("contain", r.message.full_name);
			});

			cy.window().its("cur_frm.doc.assigned_by").should("eq", cy.config("testUser"));

			// invalid input
			cy.get("@input").clear().type("invalid input", { delay: 100 }).blur();
			cy.get(".frappe-control[data-fieldname=assigned_by_full_name] .control-value").should(
				"contain",
				""
			);

			cy.window().its("cur_frm.doc.assigned_by").should("eq", undefined);

			// set valid value again
			cy.get("@input").clear().focus();
			// Wait for dropdown to appear (request might be cached)
			cy.get("@input").parent().findByRole("listbox").should("be.visible");
			cy.wait(200);
			cy.get("@input").type(cy.config("testUser"), { delay: 100 }).blur();
			cy.wait("@validate_link");

			cy.window().its("cur_frm.doc.assigned_by").should("eq", cy.config("testUser"));

			// clear input
			cy.get("@input").clear().blur();
			cy.get(".frappe-control[data-fieldname=assigned_by_full_name] .control-value").should(
				"contain",
				""
			);

			cy.window().its("cur_frm.doc.assigned_by").should("eq", "");
		});
	});

	it("should set default values", () => {
		cy.insert_doc(
			"Property Setter",
			{
				doctype_or_field: "DocField",
				doc_type: "ToDo",
				field_name: "assigned_by",
				property: "default",
				property_type: "Text",
				value: cy.config("testUser"),
			},
			true
		);
		cy.reload();
		cy.new_form("ToDo");
		cy.fill_field("description", "new", "Text Editor").blur().wait(200);
		cy.save();
		cy.call("frappe.client.get_value", {
			doctype: "User",
			filters: {
				name: cy.config("testUser"),
			},
			fieldname: "full_name",
		}).then((r) => {
			cy.get(".frappe-control[data-fieldname=assigned_by_full_name] .control-value").should(
				"contain",
				r.message.full_name
			);
		});

		// if user clears default value explicitly, system should not reset default again
		cy.get_field("assigned_by").clear().blur();
		cy.save();
		cy.get_field("assigned_by").should("have.value", "");
		cy.get(".frappe-control[data-fieldname=assigned_by_full_name] .control-value").should(
			"contain",
			""
		);
	});

	it("show translated text for Gender link field with language de with input in de", () => {
		cy.call("frappe.tests.ui_test_helpers.insert_translations").then(() => {
			cy.set_value("User", test_user(), { language: "de" });

			cy.clear_cache();
			cy.wait(500);

			get_dialog_with_gender_link().as("dialog");

			cy.get(".frappe-control[data-fieldname=link] input").focus().as("input");
			// Wait for dropdown to appear (request might be cached)
			cy.get("@input").parent().findByRole("listbox").should("be.visible");
			cy.wait(200);
			cy.get("@input").type("Sonstiges", { delay: 100 });
			// Wait for dropdown to update with search results
			cy.wait(500);
			cy.get(".frappe-control[data-fieldname=link] ul").should("be.visible");
			cy.get(".frappe-control[data-fieldname=link] input").type("{enter}");
			cy.get(".frappe-control[data-fieldname=link] input").blur();
			cy.get("@dialog").then((dialog) => {
				let field = dialog.get_field("link");
				let value = field.get_value();
				let label = field.get_label_value();

				expect(value).to.eq("Other");
				expect(label).to.eq("Sonstiges");
			});
		});
	});

	it("show text for Gender link field with language en", () => {
		cy.set_value("User", test_user(), { language: "en" });

		cy.clear_cache();
		cy.wait(1000);

		get_dialog_with_gender_link().as("dialog");

		cy.get(".frappe-control[data-fieldname=link] input").focus().as("input");
		// Wait for dropdown to appear (request might be cached)
		cy.get("@input").parent().findByRole("listbox").should("be.visible");
		cy.wait(200);
		cy.get("@input").type("Non-Conforming", { delay: 100 });
		// Wait for dropdown to update with search results
		cy.wait(500);
		cy.get(".frappe-control[data-fieldname=link] ul").should("be.visible");
		cy.get(".frappe-control[data-fieldname=link] input").type("{enter}");
		cy.get(".frappe-control[data-fieldname=link] input").blur();
		cy.get("@dialog").then((dialog) => {
			let field = dialog.get_field("link");
			let value = field.get_value();
			let label = field.get_label_value();

			expect(value).to.eq("Non-Conforming");
			expect(label).to.eq("Non-Conforming");
		});
	});

	it("show custom link option", () => {
		cy.window()
			.its("frappe")
			.then((frappe) => {
				frappe.ui.form.ControlLink.link_options = (link) => {
					return [
						{
							html:
								"<span class='text-primary custom-link-option'>" +
								frappe.utils.icon("search", "xs", "", "margin-right: 5px;") +
								" Custom Link Option" +
								"</span>",
							label: "Custom Link Option",
							value: "custom__link_option",
							action: () => {},
						},
					];
				};

				get_dialog_with_link().as("dialog");
				cy.get(".frappe-control[data-fieldname=link] input").focus().as("input");
				cy.get("@input").type("custom", { delay: 100 });
				cy.get(".custom-link-option").should("be.visible");
			});
	});

	it("keeps list format filters when merging link filters", () => {
		cy.dialog({
			title: "Link",
			fields: [
				{
					label: "Select ToDo",
					fieldname: "link",
					fieldtype: "Link",
					options: "ToDo",
					link_filters: '[["ToDo", "status", "=", "Closed"]]',
					get_query: () => ({
						filters: [
							["ToDo", "status", "=", "Open"],
							["ToDo", "priority", "=", "High"],
							["Communication", "status", "=", "Open"],
							["description", "like", "%test todo%"],
						],
					}),
				},
			],
		}).as("dialog");

		cy.wait(500);

		cy.get("@dialog").then((dialog) => {
			let filters = dialog.get_field("link").get_search_args("").filters;

			expect(filters).to.deep.eq([
				["ToDo", "priority", "=", "High"],
				["Communication", "status", "=", "Open"],
				["description", "like", "%test todo%"],
				["status", "=", "Closed"],
			]);
		});
	});
});
