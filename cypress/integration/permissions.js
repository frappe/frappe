context.skip("Permissions API", () => {
	before(() => {
		cy.visit("/login");
		cy.remove_role("frappe@example.com", "System Manager");
		cy.visit("/desk");
	});

	it("Checks permissions via `has_perm` for Kanban Board DocType", () => {
		cy.visit("/desk/kanban-board/view/list");
		cy.window()
			.its("frappe")
			.then((frappe) => {
				frappe.model.with_doctype("Kanban Board", function () {
					// needed to make sure doc meta is loaded
					expect(frappe.perm.has_perm("Kanban Board", 0, "read")).to.equal(true);
					expect(frappe.perm.has_perm("Kanban Board", 0, "write")).to.equal(true);
					expect(frappe.perm.has_perm("Kanban Board", 0, "print")).to.equal(false);
				});
			});
	});

	it("Checks permissions via `get_perm` for Kanban Board DocType", () => {
		cy.visit("/desk/kanban-board/view/list");
		cy.window()
			.its("frappe")
			.then((frappe) => {
				frappe.model.with_doctype("Kanban Board", function () {
					// needed to make sure doc meta is loaded
					const perms = frappe.perm.get_perm("Kanban Board");
					expect(perms.read).to.equal(true);
					expect(perms.write).to.equal(true);
					expect(perms.rights_without_if_owner).to.include("read");
				});
			});
	});

	after(() => {
		cy.add_role("frappe@example.com", "System Manager");
		cy.call("logout");
	});
});

context("Permissions before a doctype's meta is loaded", () => {
	before(() => {
		cy.login("frappe@example.com");
		cy.visit("/app");
	});

	it("Resolves delete for ToDo before its meta is loaded", () => {
		cy.window()
			.then((win) => {
				const { frappe, locals } = win;

				delete locals.DocType["ToDo"];
				delete frappe.perm.doctype_perm["ToDo"];

				expect(frappe.get_meta("ToDo")).to.not.exist;
				expect(frappe.perm.has_perm("ToDo", 0, "delete")).to.equal(true);

				return new Promise((resolve) => frappe.model.with_doctype("ToDo", resolve));
			})
			.then(() => {
				cy.window().then((win) => {
					expect(win.frappe.get_meta("ToDo")).to.exist;
					expect(win.frappe.perm.has_perm("ToDo", 0, "delete")).to.equal(true);
				});
			});
	});

	after(() => {
		cy.call("logout");
	});
});
