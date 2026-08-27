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
<<<<<<< HEAD
=======

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

	it("keeps selected rows checked after a list rerender", { scrollBehavior: false }, () => {
		cy.go_to_list("ToDo");
		cy.clear_filters();
		let selected_docname;

		// Step 1: select one visible row and capture its source-of-truth docname.
		cy.get(".list-row-checkbox").first().click();

		cy.window()
			.its("cur_list")
			.then((list) => {
				const selected_docnames = Array.from(list.checked_docnames);
				expect(selected_docnames.length).to.equal(1);

				// Step 2: force a list rerender; the same row should still resolve as checked.
				selected_docname = selected_docnames[0];
				list.render_list();
			});

		cy.window()
			.its("cur_list")
			.should((list) => {
				const $checkbox = list.find_checkbox_by_docname(selected_docname);
				expect($checkbox.length).to.equal(1);
				expect($checkbox.prop("checked")).to.equal(true);
			});
	});

	it(
		"preserves select-all across virtualized window rerenders",
		{ scrollBehavior: false },
		() => {
			cy.go_to_list("ToDo");
			cy.clear_filters();

			// Step 1: force virtual mode even on small fixtures to exercise virtualization path.
			cy.window()
				.its("cur_list")
				.then((list) => {
					expect(list.data.length).to.be.greaterThan(0);
					list.virtualization_threshold = 1;
					list.render_list();
				});

			// Step 2: select all and verify Set tracks all docs, not just visible DOM rows.
			cy.get('.list-row-container[data-virtual-row="1"]').should("exist");
			cy.get(".list-header-subject .list-subject .list-check-all").click();

			cy.window()
				.its("cur_list")
				.then((list) => {
					expect(list.checked_docnames.size).to.equal(list.data.length);
				});

			// Step 3: scroll to trigger window swap; selection state must remain intact.
			cy.get(".result-container").scrollTo("bottom", {
				duration: 0,
				ensureScrollable: false,
			});
			cy.wait(150);
			cy.window()
				.its("cur_list")
				.then((list) => list.render_virtual_rows(true));

			cy.window()
				.its("cur_list")
				.then((list) => {
					expect(list.checked_docnames.size).to.equal(list.data.length);
				});

			cy.get(".result-container .list-row-checkbox:checked").should("exist");
		}
	);

	it(
		"keeps mobile virtual rows rendered during fast downward scroll",
		{ scrollBehavior: false },
		() => {
			cy.viewport("iphone-6");
			cy.go_to_list("ToDo");
			cy.clear_filters();

			cy.window()
				.its("cur_list")
				.then((list) => {
					expect(list.data.length).to.be.greaterThan(0);
					list.virtualization_threshold = 1;
					list.render_list();
				});

			cy.get('.list-row-container[data-virtual-row="1"]').should("exist");

			cy.get(".result-container").scrollTo("bottom", {
				duration: 0,
				ensureScrollable: false,
			});

			cy.wait(150);
			cy.window()
				.its("cur_list")
				.then((list) => list.render_virtual_rows(true));

			cy.get('.list-row-container[data-virtual-row="1"] .list-row')
				.should("exist")
				.and("have.length.greaterThan", 0);

			cy.window()
				.its("cur_list")
				.then((list) => {
					expect(list.virtualization_state.end).to.be.greaterThan(
						list.virtualization_state.start
					);
				});
		}
	);
>>>>>>> 21b91b1 (test(list-view): cover translated field labels in bulk edit dialog)
});
