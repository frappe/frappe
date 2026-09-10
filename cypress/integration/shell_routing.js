// The shell segment of a desk URL: `/desk/build/todo` is the ToDo list in the Build shell.
//
// Most of this drives the parser directly rather than navigating, because what is under test is
// the grammar and the interesting cases are the ambiguous ones. `/desk/build/todo` and
// `/desk/todo/TODO-0001` are both two segments, so their shape cannot tell them apart, and every
// case below is a way that can go wrong. Navigating to each would test the same rule far more
// slowly and would say less about why it passed.
//
// Only shells frappe itself ships are named, so this runs on a site with nothing else installed.

describe("Desk URL shell segment", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/todo");
	});

	it("reads a shell off a route only when what follows names something", () => {
		cy.window().then((win) => {
			const router = win.frappe.router;
			const read = (segments) => [
				router.take_shell_from(segments.slice()),
				router.current_shell,
			];

			// A shell, then a doctype: the shell comes off and the rest routes as it always did.
			expect(read(["build", "todo"])).to.deep.eq([["todo"], "Build"]);
			expect(read(["build", "todo", "TODO-0001"])).to.deep.eq([
				["todo", "TODO-0001"],
				"Build",
			]);
			expect(read(["build", "todo", "view", "report"])).to.deep.eq([
				["todo", "view", "report"],
				"Build",
			]);

			// Nothing in front, so nothing is taken and this is the form it has always been.
			expect(read(["todo", "TODO-0001"])).to.deep.eq([["todo", "TODO-0001"], null]);

			// `Workflow` names both a module with a sidebar and a doctype, so the first segment is
			// a shell slug either way and only the second can decide. A document's name is not
			// something the desk routes to on its own, so the route is left whole.
			expect(read(["workflow", "WF-0001"])).to.deep.eq([["workflow", "WF-0001"], null]);
			expect(read(["workflow", "workflow"])).to.deep.eq([["workflow"], "Workflow"]);

			// One segment is never a shell. Every workspace route the desk has ever had is one
			// segment, and 31 of them collide with a shell slug on a site with erpnext installed.
			expect(read(["build"])).to.deep.eq([["build"], null]);

			// A shell nobody has is not a shell.
			expect(read(["not-a-shell", "todo"])).to.deep.eq([["not-a-shell", "todo"], null]);
		});
	});

	it("keeps `private` reserved, even once a Private shell exists", () => {
		// `/desk/private/<workspace>` names a user's own workspace and always has. A `Private`
		// module with a sidebar of its own would land on the same segment, and reading it as a
		// shell would turn `/desk/private/settings` into the public workspace of that name. The
		// shell is added here because frappe alone ships none, and the guard is what is under
		// test, not whether this site happens to trip it.
		cy.window().then((win) => {
			const router = win.frappe.router;
			const shells = win.frappe.boot.module_sidebars;
			// A site with hrms already has one; put it back as it was rather than deleting it.
			const before = shells["Private"];
			shells["Private"] = { name: "Private", module: "Private", items: [] };
			router.setup_shell_routes();

			expect(router.shell_routes["private"]).to.eq(undefined);
			expect(router.take_shell_from(["private", "todo"])).to.deep.eq(["private", "todo"]);
			expect(router.current_shell).to.eq(null);

			if (before) shells["Private"] = before;
			else delete shells["Private"];
			router.setup_shell_routes();
		});
	});

	it("spells an ampersand out rather than encoding it", () => {
		// hrms names two shells with an `&`, since a module folder is an imported Python package
		// and cannot hold one. `%26` in a path is not something anyone types or reads.
		cy.window().then((win) => {
			expect(win.frappe.router.shell_slug("Shift & Attendance")).to.eq(
				"shift-and-attendance"
			);
			expect(win.frappe.router.shell_slug("Build")).to.eq("build");
		});
	});

	it("honours a shell only when it can show what the route names", () => {
		cy.window().then((win) => {
			const sidebar = win.frappe.app.sidebar;
			const router = win.frappe.router;
			const route = ["List", "ToDo", "List"];

			// `Build` lists ToDo, which is somebody having put it there on purpose.
			router.current_shell = "Build";
			expect(sidebar.shell_from_url(route)).to.eq("Build");

			// `Users` does not list ToDo, but both are frappe's, and a shell holds across the app
			// it belongs to. This is what stops a link moving the sidebar underneath you.
			router.current_shell = "Users";
			expect(sidebar.shell_from_url(route)).to.eq("Users");

			// A shell this user does not have says nothing at all.
			router.current_shell = "Not A Real Shell";
			expect(sidebar.shell_from_url(route)).to.eq(null);

			router.current_shell = null;
		});
	});

	it("shows the shell the URL names", () => {
		cy.visit("/desk/build/todo");
		cy.get(".body-sidebar").should("have.attr", "data-title", "Build");
	});

	it("keeps a shell that does not list the entity but belongs to its app", () => {
		// `Users` is where `User` opens when nothing says otherwise, and `Build` does not list it.
		// Arriving from the Build shell keeps you there anyway, the same way navigating inside one
		// app already does.
		cy.visit("/desk/build/user");
		cy.get(".body-sidebar").should("have.attr", "data-title", "Build");
	});
});
