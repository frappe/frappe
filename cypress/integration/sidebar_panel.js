// The drawer that opens beside the body sidebar: `frappe.ui.SidebarPanel` and the
// `frappe.ui.sidebar_panels` registry that decides which one is showing.
//
// What is asserted here is the behaviour the registry took over from the two panels, which
// is the part a screenshot cannot check: only one panel open at a time, Escape closing it,
// aria-expanded tracking on the trigger, and the dock's bell driving the same panel as the
// sidebar's. Before this was one component, each panel dismissed itself and the two had
// drifted, so this is the part most likely to regress quietly.
//
// The panels are registered by the features that own them, and background tasks only shows
// its trigger when the site has tasks, so the registry is driven directly here rather than
// through the buttons. Opening through the sidebar bell is covered on its own below, since
// the wiring from a trigger to the registry is the other half of what could break.

context("Sidebar Panel", () => {
	before(() => {
		cy.login();
		// Not /app: that is the apps screen, which hides the body sidebar, and with it the
		// container the panels mount in.
		cy.visit("/app/todo");
	});

	beforeEach(() => {
		cy.window().then((win) => win.frappe.ui.sidebar_panels.close_all());
	});

	it("registers the notification panel", () => {
		cy.window().its("frappe.ui.sidebar_panels.panels.notifications").should("exist");
	});

	it("mounts the panel beside the sidebar, not inside it", () => {
		// It is a sibling of .body-sidebar so the container's width positions it, which is
		// what lets one `left: 100%` cover expanded, collapsed and mobile.
		cy.get(".body-sidebar-container > .sidebar-panel").should("exist");
		cy.get(".body-sidebar .sidebar-panel").should("not.exist");
	});

	it("opens and closes on toggle", () => {
		cy.get(".sidebar-panel-notifications").should("have.class", "hidden");
		cy.window().then((win) => win.frappe.ui.sidebar_panels.toggle("notifications"));
		cy.get(".sidebar-panel-notifications").should("not.have.class", "hidden");
		cy.window().then((win) => win.frappe.ui.sidebar_panels.toggle("notifications"));
		cy.get(".sidebar-panel-notifications").should("have.class", "hidden");
	});

	it("closes on Escape", () => {
		cy.window().then((win) => win.frappe.ui.sidebar_panels.show("notifications"));
		cy.get(".sidebar-panel-notifications").should("not.have.class", "hidden");
		cy.get("body").type("{esc}");
		cy.get(".sidebar-panel-notifications").should("have.class", "hidden");
	});

	it("closes when clicked outside", () => {
		cy.window().then((win) => win.frappe.ui.sidebar_panels.show("notifications"));
		cy.get(".sidebar-panel-notifications").should("not.have.class", "hidden");
		// Dispatched on body rather than clicking a page element: the centre of a workspace
		// is real content, and clicking it navigates, which takes the sidebar with it.
		cy.window().then((win) => win.document.body.click());
		cy.get(".sidebar-panel-notifications").should("have.class", "hidden");
	});

	it("stays open when clicked inside", () => {
		cy.window().then((win) => win.frappe.ui.sidebar_panels.show("notifications"));
		cy.get(".sidebar-panel-notifications .panel-title").click();
		cy.get(".sidebar-panel-notifications").should("not.have.class", "hidden");
	});

	it("closes from the panel's own close button", () => {
		cy.window().then((win) => win.frappe.ui.sidebar_panels.show("notifications"));
		cy.get(".sidebar-panel-notifications .panel-close").click();
		cy.get(".sidebar-panel-notifications").should("have.class", "hidden");
	});

	it("keeps aria-expanded on the trigger in step", () => {
		cy.get(".sidebar-notification").first().should("have.attr", "aria-expanded", "false");
		cy.window().then((win) => win.frappe.ui.sidebar_panels.show("notifications"));
		cy.get(".sidebar-notification").first().should("have.attr", "aria-expanded", "true");
		cy.window().then((win) => win.frappe.ui.sidebar_panels.close_all());
		cy.get(".sidebar-notification").first().should("have.attr", "aria-expanded", "false");
	});

	it("only lets one panel be open", () => {
		// Registered by the feature, so build one here rather than depending on the site
		// having background tasks for its trigger to appear.
		cy.window().then((win) => {
			new win.frappe.ui.SidebarPanel({ name: "cy-other", title: "Other" });
			win.frappe.ui.sidebar_panels.show("notifications");
		});
		cy.get(".sidebar-panel-notifications").should("not.have.class", "hidden");

		cy.window().then((win) => win.frappe.ui.sidebar_panels.show("cy-other"));
		cy.get(".sidebar-panel-cy-other").should("not.have.class", "hidden");
		cy.get(".sidebar-panel-notifications").should("have.class", "hidden");
	});

	it("closes on navigation", () => {
		cy.window().then((win) => win.frappe.ui.sidebar_panels.show("notifications"));
		cy.get(".sidebar-panel-notifications").should("not.have.class", "hidden");
		// Routed rather than re-visited: a reload would rebuild the panel hidden and pass
		// without the page-change handler doing anything.
		cy.window().then((win) => win.frappe.set_route("List", "Note"));
		cy.get(".sidebar-panel-notifications").should("have.class", "hidden");
	});

	it("gives the rail its own background-tasks trigger", () => {
		// Rendered whether or not the site has any; BackgroundTasks un-hides every trigger
		// once it has fetched a non-empty list.
		cy.get(".dock .sidebar-background-tasks").should("exist");
	});

	it("opens the background tasks panel from the rail", () => {
		// Forced because the button is hidden on a site with no tasks, and this is about the
		// wiring from the rail to the registry, not about the button's visibility.
		cy.get(".dock .sidebar-background-tasks").click({ force: true });
		cy.get(".sidebar-panel-background-tasks").should("not.have.class", "hidden");
	});

	it("opens from the sidebar bell", () => {
		// The bell is only drawn on an app without a dock; the rail carries it otherwise.
		cy.get("body").then(($body) => {
			if ($body.hasClass("dock-active")) {
				cy.get(".dock .sidebar-notification").click();
			} else {
				cy.get(".standard-items-band .sidebar-notification").click();
			}
		});
		cy.get(".sidebar-panel-notifications").should("not.have.class", "hidden");
	});
});
