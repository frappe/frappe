context("View", () => {
	before(() => {
		cy.login();
		cy.visit("/app/website");
	});

	it("Route to ToDo List View", () => {
		cy.visit("/app/todo/view/list");
		cy.wait(500);
		cy.window()
			.its("cur_list")
			.then((list) => {
				expect(list.view_name).to.equal("List");
			});
	});

	it("Route to ToDo Report View", () => {
		cy.visit("/app/todo/view/report");
		cy.wait(500);
		cy.window()
			.its("cur_list")
			.then((list) => {
				expect(list.view_name).to.equal("Report");
			});
	});

	it("Route to ToDo Dashboard View", () => {
		cy.visit("/app/todo/view/dashboard");
		cy.wait(500);
		cy.window()
			.its("cur_list")
			.then((list) => {
				expect(list.view_name).to.equal("Dashboard");
			});
	});

	it("Route to ToDo Gantt View", () => {
		cy.visit("/app/todo/view/gantt");
		cy.wait(500);
		cy.window()
			.its("cur_list")
			.then((list) => {
				expect(list.view_name).to.equal("Gantt");
			});
	});

	it("Route to ToDo Kanban View", () => {
		cy.visit("/app/todo/view/kanban");
		cy.wait(500);
		cy.window()
			.its("cur_list")
			.then((list) => {
				expect(list.view_name).to.equal("Kanban");
			});
	});

	it("Route to ToDo Calendar View", () => {
		cy.visit("/app/todo/view/calendar");
		cy.wait(500);
		cy.window()
			.its("cur_list")
			.then((list) => {
				expect(list.view_name).to.equal("Calendar");
			});
	});

	it("Route to Custom Tree View", () => {
		cy.call("frappe.tests.ui_test_helpers.setup_tree_doctype").then(() => {
			cy.visit("/app/custom-tree/view/tree");
			cy.wait(500);
			cy.window()
				.its("cur_tree")
				.then((list) => {
					expect(list.view_name).to.equal("Tree");
				});
		});
	});

	it("Route to Custom Image View", () => {
		cy.call("frappe.tests.ui_test_helpers.setup_image_doctype").then(() => {
			cy.visit("app/custom-image/view/image");
			cy.wait(500);
			cy.window()
				.its("cur_list")
				.then((list) => {
					expect(list.view_name).to.equal("Image");
				});
		});
	});

	it("Route to Communication Inbox View", () => {
		cy.call("frappe.tests.ui_test_helpers.setup_inbox").then(() => {
			cy.visit("app/communication/view/inbox");
			cy.wait(500);
			cy.window()
				.its("cur_list")
				.then((list) => {
					expect(list.view_name).to.equal("Inbox");
				});
		});
	});

	it("Re-route to default view", () => {
		cy.call("frappe.tests.ui_test_helpers.setup_default_view", { view: "Report" }).then(() => {
			cy.visit("app/event");
			cy.wait(500);
			cy.window()
				.its("cur_list")
				.then((list) => {
					expect(list.view_name).to.equal("Report");
				});
		});
	});

	it("Route to default view from app/{doctype}", () => {
		cy.call("frappe.tests.ui_test_helpers.setup_default_view", { view: "Report" }).then(() => {
			cy.visit("/app/event");
			cy.wait(500);
			cy.window()
				.its("cur_list")
				.then((list) => {
					expect(list.view_name).to.equal("Report");
				});
		});
	});

	it("Route to default view from app/{doctype}/view", () => {
		cy.call("frappe.tests.ui_test_helpers.setup_default_view", { view: "Report" }).then(() => {
			cy.visit("/app/event/view");
			cy.wait(500);
			cy.window()
				.its("cur_list")
				.then((list) => {
					expect(list.view_name).to.equal("Report");
				});
		});
	});

	it("Force Route to default view from app/{doctype}", () => {
		cy.call("frappe.tests.ui_test_helpers.setup_default_view", {
			view: "Report",
			force_reroute: true,
		}).then(() => {
			cy.visit("/app/event");
			cy.wait(500);
			cy.window()
				.its("cur_list")
				.then((list) => {
					expect(list.view_name).to.equal("Report");
				});
		});
	});

	it("Force Route to default view from app/{doctype}/view", () => {
		cy.call("frappe.tests.ui_test_helpers.setup_default_view", {
			view: "Report",
			force_reroute: true,
		}).then(() => {
			cy.visit("/app/event/view");
			cy.wait(500);
			cy.window()
				.its("cur_list")
				.then((list) => {
					expect(list.view_name).to.equal("Report");
				});
		});
	});

	it("Force Route to default view from app/{doctype}/view", () => {
		cy.call("frappe.tests.ui_test_helpers.setup_default_view", {
			view: "Report",
			force_reroute: true,
		}).then(() => {
			cy.visit("/app/event/view/list");
			cy.wait(500);
			cy.window()
				.its("cur_list")
				.then((list) => {
					expect(list.view_name).to.equal("Report");
				});
		});
	});

	it("Validate Route History for Default View", () => {
		cy.call("frappe.tests.ui_test_helpers.setup_default_view", { view: "Report" }).then(() => {
			cy.visit("/app/event");
			cy.visit("/app/event/view/list");
			cy.wait(500);
			cy.location("pathname").should("eq", "/app/event/view/list");
			cy.go("back");
			cy.location("pathname").should("eq", "/app/event");
			cy.go("back");
			cy.location("pathname").should("eq", "/app/website");
		});
	});

	it("Route to Form", () => {
		cy.call("frappe.tests.ui_test_helpers.create_note").then(() => {
			cy.visit("/app/note/Routing Test");
			cy.window()
				.its("cur_frm")
				.then((frm) => {
					expect(frm.doc.title).to.equal("Routing Test");
				});
		});
	});

	it("Route to Settings Workspace", () => {
		cy.visit("/app/settings");
		cy.get(".title-text").should("contain", "Settings");
	});
});
