const test_button_names = [
	"Metallica",
	"Pink Floyd",
	"Porcupine Tree (the GOAT)",
	"AC / DC",
	`Electronic Dance "music"`,
	"l'imperatrice",
];

const add_button = (label, group = "TestGroup") => {
	cy.window()
		.its("cur_frm")
		.then((frm) => {
			frm.add_custom_button(label, () => {}, group);
		});
};

const check_button_count = (label, group = "TestGroup") => {
	// the group opens an espresso menu; the hidden item store keeps one
	// element per label (the dedupe contract)
	cy.get(`[data-label="${encodeURIComponent(label)}"]`).should("have.length", 1);
	cy.findByRole("button", { name: group }).click();
	cy.get('.es-menu [role="menuitem"]')
		.filter((_, el) => el.textContent.trim() === label)
		.should("have.length", 1)
		.should("be.visible")
		.first()
		// buttons aren't typeable — keyboard goes through trigger (see
		// the es_components spec convention)
		.trigger("keydown", { key: "Escape" });

	// Mobile: the ... menu shows the group as a nested submenu row
	cy.viewport(420, 900);
	const dropdown_btn_label = `${group} > ${label}`;
	cy.get(`[data-label="${encodeURIComponent(dropdown_btn_label)}"]`).should("have.length", 1);
	cy.get(".menu-btn-group > button").click();
	cy.get('.es-menu [role="menuitem"]')
		.filter((_, el) => el.textContent.trim() === group)
		.should("have.length", 1)
		.click();
	cy.get('.es-menu [role="menuitem"]')
		.filter((_, el) => el.textContent.trim() === label)
		.should("have.length", 1)
		.should("be.visible");
	cy.get("body").type("{esc}");

	//reset viewport
	cy.viewport(Cypress.config("viewportWidth"), Cypress.config("viewportHeight"));
};

const click_frappe_call_button = (label, call_opts) => {
	const button = `button[data-label="${encodeURIComponent(label)}"]`;
	cy.intercept(`**/api/method/${call_opts.method}`).as("call");
	cy.window().then((win) => {
		win.cur_frm.add_custom_button(label, () => win.frappe.call(call_opts));
	});
	cy.get(button).click();
	cy.wait("@call");
	cy.get(button).should("not.have.attr", "aria-busy");
};

describe(
	"Custom group button behaviour on desk",
	{ scrollBehavior: false }, // speeds up the test
	() => {
		before(() => {
			cy.login();
			cy.visit(`/desk/note/new`, {
				onBeforeLoad: (win) => {
					win.localStorage.setItem("sidebar-expanded", "false");
				},
			});
		});

		test_button_names.forEach((button_name) => {
			it(`Custom button works with name '${button_name}'`, () => {
				add_button(button_name);
				check_button_count(button_name);

				// duplicate button shouldn't be added
				add_button(button_name);
				check_button_count(button_name);
			});
		});

		it("Clears the busy state when the callback returns a frappe.call", () => {
			click_frappe_call_button("Deferred Button", { method: "frappe.auth.get_logged_user" });
		});

		it("Clears the busy state when the frappe.call fails", () => {
			click_frappe_call_button("Failing Deferred Button", {
				method: "frappe.client.get",
				args: { doctype: "Note", name: "does-not-exist" },
			});
			cy.get("@call").its("response.statusCode").should("eq", 404);
		});
	}
);
