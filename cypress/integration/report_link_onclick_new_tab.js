context("Report cell link_onclick opens in new tab (#17870)", () => {
	// frappe.form.formatters.Link renders `<a onclick="...">` for any report
	// or list column that sets `column.link_onclick` (e.g. ERPNext's
	// financial statement account-name drilldown links). This is the single
	// shared renderer every such link goes through, in any app, so testing
	// it here covers all of them without needing a real report/app.
	const render_link_onclick_cell = (win) => {
		const docfield = {
			options: "ToDo",
			link_onclick: "frappe.set_route('List', 'ToDo', 'Report')",
		};
		const html = win.frappe.form.formatters.Link("Test Cell", docfield, {}, {});
		return win.$(html).appendTo(win.document.body);
	};

	before(() => {
		cy.login();
	});

	it("plain click still navigates in the same tab", () => {
		cy.visit("/desk/todo");

		cy.window().then((win) => {
			cy.stub(win, "open").as("windowOpen");
			cy.wrap(render_link_onclick_cell(win)).as("cell");
		});

		cy.get("@cell").click();
		cy.location("pathname").should("eq", "/desk/todo/view/report");
		cy.get("@windowOpen").should("not.have.been.called");
	});

	it("Ctrl/Cmd+click opens the link in a new tab instead", () => {
		cy.visit("/desk/todo");

		cy.window().then((win) => {
			cy.stub(win, "open").as("windowOpen");
			cy.wrap(render_link_onclick_cell(win)).as("cell");
		});

		cy.get("@cell").click({ metaKey: true, ctrlKey: true });

		cy.get("@windowOpen")
			.should("have.been.calledOnce")
			.its("firstCall.args.0")
			.should("include", "/desk/todo/view/report");
		// current tab must stay on the list, not follow the link
		cy.location("pathname").should("eq", "/desk/todo");
	});
});
