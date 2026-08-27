context("List View", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.xcall("frappe.tests.ui_test_helpers.setup_workflow");
			});
	});

	it("Keep checkbox checked after Refresh", { scrollBehavior: false }, () => {
		cy.go_to_list("ToDo");
		cy.clear_filters();
		cy.get(".list-header-subject .list-subject .list-check-all").click();
		cy.get("button[data-original-title='Reload List']").click();
		cy.get(".list-row-container .list-row-checkbox:checked").should("be.visible");
	});

	it("keeps a Check '= No' standard filter applied", { scrollBehavior: false }, () => {
		cy.go_to_list("Web Page");
		cy.clear_filters();
		cy.window().then((win) => {
			win.frappe.route_options = { published: ["=", 0] };
			win.frappe.set_route("List", "Web Page");
		});
		cy.get(".filter-selector .filter-button .button-label").should("contain", "Filters");
		cy.window()
			.its("cur_list.filter_area")
			.then((filter_area) => {
				const has_published_no = filter_area
					.get()
					.some((f) => f[1] === "published" && String(f[3]) === "0");
				expect(has_published_no, "published = No filter applied").to.be.true;
			});
	});

	it('enables "Actions" button', { scrollBehavior: false }, () => {
		const actions = [
			"Approve",
			"Reject",
			"Copy to Clipboard",
			"Export",
			"Assign To",
			"Clear Assignment",
			"Apply Assignment Rule",
			"Add Tags",
			"Print",
		];
		cy.go_to_list("ToDo");
		cy.clear_filters();
		cy.get(".list-header-subject .list-subject .list-check-all").click();
		cy.findByRole("button", { name: "Actions" }).click();
		cy.get(".dropdown-menu li:visible .dropdown-item")
			.should("have.length", 9)
			.each((el, index) => {
				cy.wrap(el).contains(actions[index]);
			})
			.then((elements) => {
				cy.intercept({
					method: "POST",
					url: "api/method/frappe.model.workflow.bulk_workflow_approval",
				}).as("bulk-approval");
				cy.wrap(elements).contains("Approve").click();
				cy.wait("@bulk-approval");
				cy.hide_dialog();
				cy.reload();
				cy.clear_filters();
				cy.get(".list-row-container:visible").should("contain", "Approved");
			});
	});

	it("Adds a button to each list view row", () => {
		// Get a ToDo with a reference name
		cy.call("frappe.client.get_value", {
			doctype: "ToDo",
			filters: {
				reference_name: ["is", "set"],
			},
			fieldname: "name",
		}).then((r) => {
			const todo_name = r.message.name;
			cy.go_to_list("ToDo");

			// Check if the 'Open' button is present in the ToDo list view
			cy.get(`.btn-default[data-name="${todo_name}"]`)
				.scrollIntoView({ inline: "center", block: "nearest" })
				.should("be.visible")
				.click();

			cy.window()
				.its("cur_frm")
				.then((frm) => {
					// Routes to the reference document
					expect(frm.doc.doctype).to.equal("ToDo");
					expect(frm.doc.name).to.not.equal(todo_name);
				});
		});
	});

	it("translates field labels in the bulk edit dialog", { scrollBehavior: false }, () => {
		const translations = {
			Route: "Routen-Pfad",
			"Web Page": "Webseite",
			"CSS Class": "CSS-Klasse",
			"Page Building Blocks": "Seitenbausteine",
		};

		cy.insert_doc(
			"Web Page",
			{ title: "Impressum", route: "impressum", content_type: "Rich Text" },
			true
		);
		cy.go_to_list("Web Page");
		cy.clear_filters();
		cy.get(".list-header-subject .list-subject .list-check-all").click();

		cy.window().then((win) => Object.assign(win.frappe._messages, translations));
		cy.click_action_button("Edit");

		cy.get_open_dialog().find('input[data-fieldname="field"]').clear().type("Routen-Pfad");
		cy.get(".awesomplete li:visible").should("contain.text", "Routen-Pfad (Webseite)");

		cy.get_open_dialog().find('input[data-fieldname="field"]').clear().type("CSS-Klasse");
		cy.get(".awesomplete li:visible").should("contain.text", "CSS-Klasse (Seitenbausteine)");

		cy.hide_dialog();
		cy.window().then((win) => {
			Object.keys(translations).forEach((key) => delete win.frappe._messages[key]);
		});
		cy.remove_doc("Web Page", "impressum");
	});
});
