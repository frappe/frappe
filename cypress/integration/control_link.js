context("Control Link", () => {
	before(() => {
		cy.login();
		cy.visit("/app/website");
	});

	beforeEach(() => {
		cy.visit("/app/website");
		cy.create_records({
			doctype: "ToDo",
			description: "this is a test todo for link",
		}).as("todos");
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

		cy.intercept("POST", "/api/method/frappe.desk.search.search_link").as("search_link");

		cy.get(".frappe-control[data-fieldname=link] input").focus().as("input");
		cy.wait("@search_link");
		cy.get("@input").type("todo for link", { delay: 200 });
		cy.wait("@search_link");
		cy.wait(500);
		cy.get(".frappe-control[data-fieldname=link]").findByRole("listbox").should("be.visible");
		cy.get(".frappe-control[data-fieldname=link] input").type("{enter}", { delay: 100 });
		cy.get(".frappe-control[data-fieldname=link] input").blur();
		cy.get("@dialog").then((dialog) => {
			cy.get("@todos").then((todos) => {
				let value = dialog.get_value("link");
				expect(value).to.eq(todos[0]);
			});
		});
	});

	it("should unset invalid value", () => {
		get_dialog_with_link().as("dialog");

		cy.intercept("/api/method/frappe.client.validate_link*").as("validate_link");

		cy.get(".frappe-control[data-fieldname=link] input")
			.type("invalid value", { delay: 100 })
			.blur();
		cy.wait("@validate_link");
		cy.wait(500);
		cy.get(".frappe-control[data-fieldname=link] input").should("have.value", "");
	});

	it("should be possible set empty value explicitly", () => {
		get_dialog_with_link().as("dialog");

		cy.intercept("/api/method/frappe.client.validate_link*").as("validate_link");

		cy.get(".frappe-control[data-fieldname=link] input").type("  ", { delay: 100 }).blur();
		cy.wait("@validate_link");
		cy.wait(500);
		cy.get(".frappe-control[data-fieldname=link] input").should("have.value", "");
		cy.window()
			.its("cur_dialog")
			.then((dialog) => {
				expect(dialog.get_value("link")).to.equal("");
			});
	});

	it("should show open link button", () => {
		get_dialog_with_link().as("dialog");

		cy.intercept("/api/method/frappe.client.validate_link*").as("validate_link");
		cy.intercept("POST", "/api/method/frappe.desk.search.search_link").as("search_link");

		cy.get("@todos").then((todos) => {
			cy.get(".frappe-control[data-fieldname=link] input").as("input");
			cy.get("@input").focus();
			cy.wait("@search_link");
			cy.get("@input").type(todos[0]).blur();
			cy.wait("@validate_link");
			cy.get("@input").trigger("mouseover");
			cy.get(".frappe-control[data-fieldname=link] .btn-open")
				.should("be.visible")
				.should("have.attr", "href", `/app/todo/${todos[0]}`);
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

		cy.intercept("POST", "/api/method/frappe.desk.search.search_link").as("search_link");

		cy.get(".frappe-control[data-fieldname=link] input").focus().as("input");
		cy.wait("@search_link");
		cy.get("@input").type("todo for link", { delay: 200 });
		cy.wait("@search_link");
		cy.get(".frappe-control[data-fieldname=link] ul").should("be.visible");
		cy.get(".frappe-control[data-fieldname=link] input").type("{enter}", { delay: 100 });
		cy.get(".frappe-control[data-fieldname=link] input").blur();
		cy.get("@dialog").then((dialog) => {
			cy.get("@todos").then((todos) => {
				let field = dialog.get_field("link");
				let value = field.get_value();
				let label = field.get_label_value();

				expect(value).to.eq(todos[0]);
				expect(label).to.eq("this is a test todo for link");
			});
		});
	});

	it("should update dependant fields (via fetch_from)", () => {
		cy.get("@todos").then((todos) => {
			cy.visit(`/app/todo/${todos[0]}`);
			cy.intercept("POST", "/api/method/frappe.desk.search.search_link").as("search_link");
			cy.intercept("/api/method/frappe.client.validate_link*").as("validate_link");

			cy.get(".frappe-control[data-fieldname=assigned_by] input").focus().as("input");
			cy.get("@input").clear().type(cy.config("testUser"), { delay: 300 }).blur();
			cy.wait("@validate_link");
			cy.get(".frappe-control[data-fieldname=assigned_by_full_name] .control-value").should(
				"contain",
				"Frappe"
			);

			cy.window().its("cur_frm.doc.assigned_by").should("eq", cy.config("testUser"));

			// invalid input
			cy.get("@input").clear().type("invalid input", { delay: 100 }).blur();
			cy.get(".frappe-control[data-fieldname=assigned_by_full_name] .control-value").should(
				"contain",
				""
			);

			cy.window().its("cur_frm.doc.assigned_by").should("eq", null);

			// set valid value again
			cy.get("@input").clear().focus();
			cy.wait("@search_link");
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
				value: "Administrator",
			},
			true
		);
		cy.reload();
		cy.new_form("ToDo");
		cy.fill_field("description", "new", "Text Editor").wait(200);
		cy.save();
		cy.get(".frappe-control[data-fieldname=assigned_by_full_name] .control-value").should(
			"contain",
			"Administrator"
		);
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
			cy.window()
				.its("frappe")
				.then((frappe) => {
					cy.set_value("User", frappe.user.name, { language: "de" });
				});

			cy.clear_cache();
			cy.wait(500);

			get_dialog_with_gender_link().as("dialog");
			cy.intercept("POST", "/api/method/frappe.desk.search.search_link").as("search_link");

			cy.get(".frappe-control[data-fieldname=link] input").focus().as("input");
			cy.wait("@search_link");
			cy.get("@input").type("Sonstiges", { delay: 200 });
			cy.wait("@search_link");
			cy.wait(500);
			cy.get(".frappe-control[data-fieldname=link] ul").should("be.visible");
			cy.get(".frappe-control[data-fieldname=link] input").type("{enter}", { delay: 100 });
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
		cy.window()
			.its("frappe")
			.then((frappe) => {
				cy.set_value("User", frappe.user.name, { language: "en" });
			});

		cy.clear_cache();
		cy.wait(1000);

		get_dialog_with_gender_link().as("dialog");
		cy.intercept("POST", "/api/method/frappe.desk.search.search_link").as("search_link");

		cy.get(".frappe-control[data-fieldname=link] input").focus().as("input");
		cy.wait("@search_link");
		cy.get("@input").type("Non-Conforming", { delay: 200 });
		cy.wait("@search_link");
		cy.wait(500);
		cy.get(".frappe-control[data-fieldname=link] ul").should("be.visible");
		cy.get(".frappe-control[data-fieldname=link] input").type("{enter}", { delay: 100 });
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
								"<i class='fa fa-search' style='margin-right: 5px;'></i> " +
								"Custom Link Option" +
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
});
