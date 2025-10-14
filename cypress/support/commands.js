import "@testing-library/cypress/add-commands";
import "@4tw/cypress-drag-drop";
import "cypress-real-events/support";
// ***********************************************
// This example commands.js shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************
//
//
// -- This is a parent command --
// Cypress.Commands.add("login", (email, password) => { ... });
//
//
// -- This is a child command --
// Cypress.Commands.add("drag", { prevSubject: 'element'}, (subject, options) => { ... });
//
//
// -- This is a dual command --
// Cypress.Commands.add("dismiss", { prevSubject: 'optional'}, (subject, options) => { ... });
//
//
// -- This is will overwrite an existing command --
// Cypress.Commands.overwrite("visit", (originalFn, url, options) => { ... });

Cypress.Commands.add("login", (email, password) => {
	if (!email) {
		email = Cypress.config("testUser") || "Administrator";
	}
	if (!password) {
		password = Cypress.env("adminPassword");
	}
	// cy.session clears all localStorage on new login, so we need to retain the last route
	const session_last_route = window.localStorage.getItem("session_last_route");
	return cy
		.session([email, password] || "", () => {
			return cy.request({
				url: "/api/method/login",
				method: "POST",
				body: {
					usr: email,
					pwd: password,
				},
			});
		})
		.then(() => {
			if (session_last_route) {
				window.localStorage.setItem("session_last_route", session_last_route);
			}
		});
});

Cypress.Commands.add("call", (method, args) => {
	return cy
		.window()
		.its("frappe.csrf_token")
		.then((csrf_token) => {
			return cy
				.request({
					url: `/api/method/${method}`,
					method: "POST",
					body: args,
					headers: {
						Accept: "application/json",
						"Content-Type": "application/json",
						"X-Frappe-CSRF-Token": csrf_token,
					},
				})
				.then((res) => {
					expect(res.status).eq(200);
					if (method === "logout") {
						Cypress.session.clearAllSavedSessions();
					}
					return res.body;
				});
		});
});

Cypress.Commands.add("get_list", (doctype, fields = [], filters = []) => {
	filters = JSON.stringify(filters);
	fields = JSON.stringify(fields);
	let url = `/api/resource/${doctype}?fields=${fields}&filters=${filters}`;
	return cy
		.window()
		.its("frappe.csrf_token")
		.then((csrf_token) => {
			return cy
				.request({
					method: "GET",
					url,
					headers: {
						Accept: "application/json",
						"X-Frappe-CSRF-Token": csrf_token,
					},
				})
				.then((res) => {
					expect(res.status).eq(200);
					return res.body;
				});
		});
});

Cypress.Commands.add("get_doc", (doctype, name) => {
	return cy
		.window()
		.its("frappe.csrf_token")
		.then((csrf_token) => {
			return cy
				.request({
					method: "GET",
					url: `/api/resource/${doctype}/${name}`,
					headers: {
						Accept: "application/json",
						"X-Frappe-CSRF-Token": csrf_token,
					},
				})
				.then((res) => {
					expect(res.status).eq(200);
					return res.body;
				});
		});
});

Cypress.Commands.add("remove_doc", (doctype, name) => {
	return cy
		.window()
		.its("frappe.csrf_token")
		.then((csrf_token) => {
			return cy
				.request({
					method: "DELETE",
					url: `/api/resource/${doctype}/${name}`,
					headers: {
						Accept: "application/json",
						"X-Frappe-CSRF-Token": csrf_token,
					},
				})
				.then((res) => {
					expect(res.status).eq(202);
					return res.body;
				});
		});
});

Cypress.Commands.add("create_records", (doc) => {
	return cy
		.call("frappe.tests.ui_test_helpers.create_if_not_exists", { doc: JSON.stringify(doc) })
		.then((r) => r.message);
});

Cypress.Commands.add("set_value", (doctype, name, obj) => {
	return cy.call("frappe.client.set_value", {
		doctype,
		name,
		fieldname: obj,
	});
});

Cypress.Commands.add("fill_field", (fieldname, value, fieldtype = "Data") => {
	cy.get_field(fieldname, fieldtype).as("input");

	if (["Date", "Time", "Datetime"].includes(fieldtype)) {
		cy.get("@input").click().wait(200);
		cy.get(".datepickers-container .datepicker.active").should("exist");
	}
	if (fieldtype === "Time") {
		cy.get("@input").clear().wait(200);
	}

	if (fieldtype === "Select") {
		cy.get("@input").select(value);
	} else {
		cy.get("@input").type(value, {
			waitForAnimations: false,
			parseSpecialCharSequences: false,
			force: true,
			delay: 100,
		});
	}
	return cy.get("@input");
});

Cypress.Commands.add("get_field", (fieldname, fieldtype = "Data") => {
	let field_element = fieldtype === "Select" ? "select" : "input";
	let selector = `[data-fieldname="${fieldname}"] ${field_element}:visible`;

	if (fieldtype === "Text Editor") {
		selector = `[data-fieldname="${fieldname}"] .ql-editor[contenteditable=true]:visible`;
	}
	if (fieldtype === "Code") {
		selector = `[data-fieldname="${fieldname}"] .ace_text-input`;
	}
	if (fieldtype === "Markdown Editor") {
		selector = `[data-fieldname="${fieldname}"] .ace-editor-target`;
	}

	return cy.get(selector).first();
});

Cypress.Commands.add(
	"fill_table_field",
	(tablefieldname, row_idx, fieldname, value, fieldtype = "Data") => {
		cy.get_table_field(tablefieldname, row_idx, fieldname, fieldtype).as("input");

		if (["Date", "Time", "Datetime"].includes(fieldtype)) {
			cy.get("@input").click().wait(200);
			cy.get(".datepickers-container .datepicker.active").should("exist");
		}
		if (fieldtype === "Time") {
			cy.get("@input").clear().wait(200);
		}

		if (fieldtype === "Select") {
			cy.get("@input").select(value);
		} else {
			cy.get("@input").type(value, { waitForAnimations: false, force: true });
		}
		return cy.get("@input");
	}
);

Cypress.Commands.add(
	"get_table_field",
	(tablefieldname, row_idx, fieldname, fieldtype = "Data") => {
		let selector = `.frappe-control[data-fieldname="${tablefieldname}"]`;
		selector += ` [data-idx="${row_idx}"]`;

		if (fieldtype === "Text Editor") {
			selector += ` [data-fieldname="${fieldname}"] .ql-editor[contenteditable=true]`;
		} else if (fieldtype === "Code") {
			selector += ` [data-fieldname="${fieldname}"] .ace_text-input`;
		} else {
			selector += ` [data-fieldname="${fieldname}"]`;
			return cy.get(selector).find(".form-control:visible, .static-area:visible").first();
		}
		return cy.get(selector);
	}
);

Cypress.Commands.add("awesomebar", (text) => {
	cy.get("#navbar-search").type(`${text}{downarrow}{enter}`, { delay: 700 });
});

Cypress.Commands.add("new_form", (doctype) => {
	let dt_in_route = doctype.toLowerCase().replace(/ /g, "-");
	cy.visit(`/app/${dt_in_route}/new`);
	cy.get("body").should(($body) => {
		const dataRoute = $body.attr("data-route");
		expect(dataRoute).to.match(new RegExp(`^Form/${doctype}/new-${dt_in_route}-`));
	});
	cy.get("body").should("have.attr", "data-ajax-state", "complete");
});

Cypress.Commands.add("select_form_tab", (label) => {
	cy.get(".form-tabs-list [data-toggle='tab']").contains(label).click().wait(500);
});

Cypress.Commands.add("go_to_list", (doctype) => {
	let dt_in_route = doctype.toLowerCase().replace(/ /g, "-");
	cy.visit(`/app/${dt_in_route}`);
});

Cypress.Commands.add("clear_cache", () => {
	cy.window()
		.its("frappe")
		.then((frappe) => {
			frappe.ui.toolbar.clear_cache();
		});
});

Cypress.Commands.add("dialog", (opts) => {
	return cy
		.window({ log: false })
		.its("frappe", { log: false })
		.then((frappe) => {
			Cypress.log({
				name: "dialog",
				displayName: "dialog",
				message: "frappe.ui.Dialog",
				consoleProps: () => {
					return {
						options: opts,
						dialog: d,
					};
				},
			});

			var d = new frappe.ui.Dialog(opts);
			d.show();
			return d;
		});
});

Cypress.Commands.add("get_open_dialog", () => {
	return cy.get(".modal:visible").last();
});

Cypress.Commands.add("save", () => {
	cy.intercept("/api/method/frappe.desk.form.save.savedocs").as("save_call");
	cy.get(`.page-container:visible button[data-label="Save"]`).click({ force: true });
	cy.wait("@save_call");
});
Cypress.Commands.add("hide_dialog", () => {
	cy.wait(500);
	cy.get_open_dialog().focus().find(".btn-modal-close").click();
	cy.get(".modal:visible").should("not.exist");
});

Cypress.Commands.add("clear_dialogs", () => {
	cy.window().then((win) => {
		win.$(".modal, .modal-backdrop").remove();
	});
	cy.get(".modal").should("not.exist");
});

Cypress.Commands.add("clear_datepickers", () => {
	cy.window().then((win) => {
		win.$(".datepicker").remove();
	});
	cy.get(".datepicker").should("not.exist");
});

Cypress.Commands.add("insert_doc", (doctype, args, ignore_duplicate) => {
	if (!args.doctype) {
		args.doctype = doctype;
	}
	return cy
		.window()
		.its("frappe.csrf_token")
		.then((csrf_token) => {
			return cy
				.request({
					method: "POST",
					url: `/api/resource/${doctype}`,
					body: args,
					headers: {
						Accept: "application/json",
						"Content-Type": "application/json",
						"X-Frappe-CSRF-Token": csrf_token,
					},
					failOnStatusCode: !ignore_duplicate,
				})
				.then((res) => {
					let status_codes = [200];
					if (ignore_duplicate) {
						status_codes.push(409);
					}

					let message = null;
					if (ignore_duplicate && !status_codes.includes(res.status)) {
						message = `Document insert failed, response: ${JSON.stringify(
							res,
							null,
							"\t"
						)}`;
					}
					expect(res.status).to.be.oneOf(status_codes, message);
					return res.body.data;
				});
		});
});

Cypress.Commands.add("update_doc", (doctype, docname, args) => {
	return cy
		.window()
		.its("frappe.csrf_token")
		.then((csrf_token) => {
			return cy
				.request({
					method: "PUT",
					url: `/api/resource/${doctype}/${docname}`,
					body: args,
					headers: {
						Accept: "application/json",
						"Content-Type": "application/json",
						"X-Frappe-CSRF-Token": csrf_token,
					},
				})
				.then((res) => {
					expect(res.status).to.eq(200);
					return res.body.data;
				});
		});
});

Cypress.Commands.add("switch_to_user", (user) => {
	cy.call("logout");
	cy.wait(200);
	cy.login(user);
	cy.reload();
});

Cypress.Commands.add("add_role", (user, role) => {
	cy.window()
		.its("frappe")
		.then((frappe) => {
			const session_user = frappe.session.user;
			add_remove_role("add", user, role, session_user);
		});
});

Cypress.Commands.add("remove_role", (user, role) => {
	cy.window()
		.its("frappe")
		.then((frappe) => {
			const session_user = frappe.session.user;
			add_remove_role("remove", user, role, session_user);
		});
});

const add_remove_role = (action, user, role, session_user) => {
	if (session_user !== "Administrator") {
		cy.switch_to_user("Administrator");
	}

	cy.call("frappe.tests.ui_test_helpers.add_remove_role", {
		action: action,
		user: user,
		role: role,
	});

	if (session_user !== "Administrator") {
		cy.switch_to_user(session_user);
	}
};

Cypress.Commands.add("open_list_filter", () => {
	cy.get(".filter-section .filter-button").click();
	cy.wait(300);
	cy.get(".filter-popover").should("exist");
});

Cypress.Commands.add("click_custom_action_button", (name) => {
	cy.get(`.custom-actions [data-label="${encodeURIComponent(name)}"]`).click();
});

Cypress.Commands.add("click_action_button", (name) => {
	cy.findByRole("button", { name: "Actions" }).click();
	cy.get(`.actions-btn-group [data-label="${encodeURIComponent(name)}"]`).click();
});

Cypress.Commands.add("click_menu_button", (name) => {
	cy.get(".standard-actions .menu-btn-group > .btn").click();
	cy.get(`.menu-btn-group [data-label="${encodeURIComponent(name)}"]`).click();
});

Cypress.Commands.add("clear_filters", () => {
	cy.get(".filter-x-button").click({ force: true });
	cy.wait(1000);
});

Cypress.Commands.add("click_modal_primary_button", (btn_name) => {
	cy.wait(400);
	cy.get(".modal-footer > .standard-actions > .btn-primary")
		.contains(btn_name)
		.click({ force: true });
});

Cypress.Commands.add("click_sidebar_button", (btn_name) => {
	cy.get(".list-group-by-fields .list-link > a").contains(btn_name).click({ force: true });
});

Cypress.Commands.add("click_listview_row_item", (row_no) => {
	cy.get(".list-row > .level-left > .list-subject > .level-item > .ellipsis")
		.eq(row_no)
		.click({ force: true });
});

Cypress.Commands.add("click_listview_row_item_with_text", (text) => {
	cy.get(".list-row > .level-left > .list-subject > .level-item > .ellipsis")
		.contains(text)
		.first()
		.click({ force: true });
});

Cypress.Commands.add("click_filter_button", () => {
	cy.get(".filter-button").click();
});

Cypress.Commands.add("click_listview_primary_button", (btn_name) => {
	cy.get(".primary-action").contains(btn_name).click({ force: true });
});

Cypress.Commands.add("click_doc_primary_button", (btn_name) => {
	cy.get(".primary-action").contains(btn_name).click({ force: true });
});

Cypress.Commands.add("click_timeline_action_btn", (btn_name) => {
	cy.get(".timeline-message-box .actions .action-btn").contains(btn_name).click();
});

Cypress.Commands.add("select_listview_row_checkbox", (row_no) => {
	cy.get(".frappe-list .select-like > .list-row-checkbox").eq(row_no).click();
});

Cypress.Commands.add("click_form_section", (section_name) => {
	cy.get(".section-head").contains(section_name).click();
});

const compare_document = (expected, actual) => {
	for (const prop in expected) {
		if (expected[prop] instanceof Array) {
			// recursively compare child documents.
			expected[prop].forEach((item, idx) => {
				compare_document(item, actual[prop][idx]);
			});
		} else {
			assert.equal(expected[prop], actual[prop], `${prop} should be equal.`);
		}
	}
};

Cypress.Commands.add("compare_document", (expected_document) => {
	cy.window()
		.its("cur_frm")
		.then((frm) => {
			// Don't remove this, cypress can't magically wait for events it has no control over.
			cy.wait(1000);
			compare_document(expected_document, frm.doc);
		});
});
