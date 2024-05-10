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
		cy.call("frappe.tests.ui_test_helpers.create_kanban").then(() => {
			cy.visit("/app/note/view/kanban/_Note _Kanban");
			cy.wait(500);
			cy.window()
				.its("cur_list")
				.then((list) => {
					expect(list.view_name).to.equal("Kanban");
				});
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

	it("Route to File View", () => {
		cy.intercept("POST", "/api/method/frappe.desk.reportview.get").as("list_loaded");
		cy.visit("app/file");
		cy.wait("@list_loaded");
		cy.window()
			.its("cur_list")
			.then((list) => {
				expect(list.view_name).to.equal("File");
				expect(list.current_folder).to.equal("Home");
			});

		cy.visit("app/file/view/home/Attachments");
		cy.wait("@list_loaded");
		cy.window()
			.its("cur_list")
			.then((list) => {
				expect(list.view_name).to.equal("File");
				expect(list.current_folder).to.equal("Home/Attachments");
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
			cy.location("pathname").should("eq", "/app/event/view/list");
			cy.go("back");
			cy.location("pathname").should("eq", "/app/event");
		});
	});

	it("Route to Form", () => {
		const test_user = cy.config("testUser");
		cy.visit(`/app/user/${test_user}`);
		cy.window()
			.its("cur_frm")
			.then((frm) => {
				expect(frm.doc.name).to.equal(test_user);
			});
	});

	it("Route to Website Workspace", () => {
		cy.visit("/app/website");
		cy.get(".title-text").should("contain", "Website");
	});
});
