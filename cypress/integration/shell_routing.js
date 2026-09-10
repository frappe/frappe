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

			// A view container that is not a `Page` record. `query-report` lives in
			// `frappe.standard_pages`, so `page_info` has never heard of it, and reading only
			// `page_info` left `/desk/<shell>/query-report/<name>` going nowhere at all.
			expect(read(["build", "query-report", "Permitted Documents For User"])).to.deep.eq([
				["query-report", "Permitted Documents For User"],
				"Build",
			]);
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

	it("writes the shell into a URL that arrived without one", () => {
		// The whole point, from a user's side: a link written before any of this existed, or by
		// hand, or by a part of the desk that never asked, still ends up naming where it opened.
		cy.visit("/desk/todo");
		cy.location("pathname").should("eq", "/desk/build/todo");
	});

	it("leaves the query string and the fragment alone while doing it", () => {
		// The path is rebuilt by putting the shell in front of what is already there, so
		// everything after it survives untouched, filters included.
		cy.visit("/desk/todo?status=Open");
		cy.location("pathname").should("eq", "/desk/build/todo");
		cy.location("search").should("eq", "?status=Open");
	});

	it("keeps the shell you are standing in as you navigate", () => {
		// `Users` does not list ToDo, but both belong to frappe, so the shell holds and the URL
		// says so. This is what stops a link moving the sidebar underneath you, and it is now
		// written down rather than remembered in the browser.
		cy.visit("/desk/users/user");
		// Wait for the sidebar itself, not just the URL. Standing in a shell is the precondition
		// here, and the URL is correct a moment before the sidebar has read it.
		cy.get(".body-sidebar").should("have.attr", "data-title", "Users");

		// Without the third argument, since `set_route("List", "ToDo", "List")` asks for the list
		// view by name and writes `/desk/todo/view/list`.
		cy.window().then((win) => win.frappe.set_route("List", "ToDo"));
		cy.location("pathname").should("eq", "/desk/users/todo");
		cy.get(".body-sidebar").should("have.attr", "data-title", "Users");
	});

	it("does not rewrite history when you go back", () => {
		// A URL outranks the sidebar on screen, or the back button would rewrite the entry it
		// just returned to: going back to a ToDo opened in Build, while standing in Users, would
		// replace it with Users.
		cy.visit("/desk/build/todo");
		cy.visit("/desk/users/user");
		cy.go("back");

		cy.location("pathname").should("eq", "/desk/build/todo");
		cy.get(".body-sidebar").should("have.attr", "data-title", "Build");
	});

	it("opens a report through a shell", () => {
		// The whole failure this was found by: `/desk/maintenance/query-report/<name>` rendered
		// nothing, because `query-report` is not a `Page` record and so read as naming nothing,
		// which left the shell in front of it un-taken and the route unparseable.
		cy.visit("/desk/build/query-report/Permitted%20Documents%20For%20User");
		cy.location("pathname").should(
			"match",
			/\/query-report\/Permitted%20Documents%20For%20User$/
		);
		cy.window()
			.its("frappe")
			.then((frappe) => {
				expect(frappe.get_route()).to.deep.eq([
					"query-report",
					"Permitted Documents For User",
				]);
			});
	});

	it("highlights the sidebar item you are looking at", () => {
		// The active item is found by comparing each item's href against the URL, as strings. Once
		// the URL carried a shell and the hrefs did not, nothing matched and nothing was ever
		// highlighted, on every sidebar at once.
		cy.visit("/desk/build/todo");
		cy.get(".body-sidebar").should("have.attr", "data-title", "Build");
		cy.get(".standard-sidebar-item.active-sidebar").should("have.length", 1);
	});

	it("builds sidebar links that already name their shell", () => {
		// The other half of the same thing: a link that arrives correct needs no rewriting, so
		// clicking one does not change the URL out from under itself.
		cy.visit("/desk/build/todo");
		cy.get(".body-sidebar").should("have.attr", "data-title", "Build");
		cy.window().then((win) => {
			const path = frappe_route(win, { link_type: "DocType", link_to: "ToDo" }, "Build");
			expect(path).to.eq("/desk/build/todo");

			// A URL item points wherever its author said, desk or not, so it is left alone.
			const external = frappe_route(
				win,
				{ link_type: "URL", url: "https://frappe.io" },
				"Build"
			);
			expect(external).to.eq("https://frappe.io");
		});
	});
});

function frappe_route(win, item, shell) {
	return win.frappe.ui.sidebar_item.get_route({ type: "Link", ...item }, false, shell);
}
