context("Realtime updates", () => {
	before(() => {
		cy.login();
	});

	beforeEach(() => {
		cy.visit("/app/todo");
		// required because immediately after load socket is still connecting.
		// Not a huge deal breaker in prod.
		cy.wait(500);
		cy.clear_filters();
	});

	it("Shows version conflict warning", { scrollBehavior: false }, () => {
		cy.insert_doc("ToDo", { description: "old" }).then((doc) => {
			cy.visit(`/app/todo/${doc.name}`);
			// make form dirty
			cy.fill_field("status", "Cancelled", "Select");

			// update doc using api - simulating parallel change by another user
			cy.update_doc("ToDo", doc.name, { status: "Closed" }).then(() => {
				cy.findByRole("button", { name: "Refresh" }).click();
				cy.get_field("status", "Select").should("have.value", "Closed");
			});
		});
	});

	it("List view updates in realtime on insert", { scrollBehavior: false }, () => {
		const original = "Added for realtime update";
		const updated = "Updated for realtime update";
		cy.insert_doc("ToDo", { description: original }).then((doc) => {
			cy.contains(original).should("be.visible");

			// update doc using api - simulating parallel change by another user
			cy.update_doc("ToDo", doc.name, { description: updated }).then(() => {
				cy.contains(updated).should("be.visible");
			});
		});
	});

	it("Receives msgprint from server", { scrollBehavior: false }, () => {
		// required because immediately after load socket is still connecting.
		// Not a deal breaker in prod
		const msg = "msgprint sent via realtime";
		publish_realtime({ event: "msgprint", message: msg }).then(() => {
			cy.contains(msg).should("be.visible");
		});
	});

	it("Recieves custom messages from server", { scrollBehavior: false }, () => {
		const event = "cypress_event";
		let handler = {
			handle() {
				console.log("clear");
			},
		};
		cy.spy(handler, "handle").as("callback");

		cy.window()
			.its("frappe")
			.then((frappe) => {
				frappe.realtime.on(event, () => handler.handle());
			});

		publish_realtime({ event }).then(() => {
			cy.get("@callback").should("be.called");
		});
	});

	it("Progress bar", { scrollBehavior: false }, () => {
		const title = "RealTime Progress";
		cy.call("frappe.tests.ui_test_helpers.publish_progress", { title }).then(() => {
			cy.contains(title).should("be.visible");
		});
	});
});

function publish_realtime(args) {
	return cy.call("frappe.tests.ui_test_helpers.publish_realtime", args);
}
