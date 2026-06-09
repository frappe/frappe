context("Realtime Backend Switcher", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
	});

	it("defaults to the node backend", () => {
		cy.window().then((win) => {
			win.localStorage.removeItem("frappe_socketio_backend");
			expect(win.frappe.realtime.get_backend()).to.equal("node");
		});
	});

	it("rejects invalid backend names without persisting or reloading", () => {
		cy.window().then((win) => {
			win.frappe.realtime.set_backend("deno");
			expect(win.localStorage.getItem("frappe_socketio_backend")).to.equal(null);
			expect(win.frappe.realtime.get_backend()).to.equal("node");
		});
	});

	it("reads the configured backend from localStorage", () => {
		cy.window().then((win) => {
			win.localStorage.setItem("frappe_socketio_backend", "python");
			expect(win.frappe.realtime.get_backend()).to.equal("python");
			win.localStorage.removeItem("frappe_socketio_backend");
		});
	});
});
