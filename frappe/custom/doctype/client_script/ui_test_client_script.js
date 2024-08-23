context("Client Script", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
	});

	it("should run form script in doctype form", () => {
		cy.insert_doc(
			"Client Script",
			{
				name: "Todo form script",
				dt: "ToDo",
				view: "Form",
				enabled: 1,
				script: `console.log('todo form script')`,
			},
			true
		);
		cy.visit("/app/todo/new", {
			onBeforeLoad(win) {
				cy.spy(win.console, "log").as("consoleLog");
			},
		});
		cy.get("@consoleLog").should("be.calledWith", "todo form script");
	});

	it("should run list script in doctype list view", () => {
		cy.insert_doc(
			"Client Script",
			{
				name: "Todo list script",
				dt: "ToDo",
				view: "List",
				enabled: 1,
				script: `console.log('todo list script')`,
			},
			true
		);
		cy.visit("/app/todo", {
			onBeforeLoad(win) {
				cy.spy(win.console, "log").as("consoleLog");
			},
		});
		cy.get("@consoleLog").should("be.calledWith", "todo list script");
	});

	it("should not run disabled scripts", () => {
		cy.insert_doc(
			"Client Script",
			{
				name: "Todo disabled list",
				dt: "ToDo",
				view: "List",
				enabled: 0,
				script: `console.log('todo disabled script')`,
			},
			true
		);
		cy.visit("/app/todo", {
			onBeforeLoad(win) {
				cy.spy(win.console, "log").as("consoleLog");
			},
		});
		cy.get("@consoleLog").should("not.be.calledWith", "todo disabled script");
	});

	it("should run multiple scripts", () => {
		cy.insert_doc(
			"Client Script",
			{
				name: "Todo form script 1",
				dt: "ToDo",
				view: "Form",
				enabled: 1,
				script: `console.log('todo form script 1')`,
			},
			true
		);
		cy.insert_doc(
			"Client Script",
			{
				name: "Todo form script 2",
				dt: "ToDo",
				view: "Form",
				enabled: 1,
				script: `console.log('todo form script 2')`,
			},
			true
		);
		cy.visit("/app/todo/new", {
			onBeforeLoad(win) {
				cy.spy(win.console, "log").as("consoleLog");
			},
		});
		cy.get("@consoleLog").should("be.calledWith", "todo form script 1");
		cy.get("@consoleLog").should("be.calledWith", "todo form script 2");
	});
});
