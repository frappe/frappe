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

			// `Workflow` names both a module with a sidebar and a doctype, and the doctype wins:
			// `/desk/workflow/<name>` has always been a Workflow form, and a Workflow may be named
			// `todo`. The parser cannot fetch the document to find out, so the route is left whole
			// even when what follows is routable on its own.
			expect(read(["workflow", "WF-0001"])).to.deep.eq([["workflow", "WF-0001"], null]);
			expect(read(["workflow", "todo"])).to.deep.eq([["workflow", "todo"], null]);

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

	it("leaves a workspace alone when it is named after its own shell", () => {
		// `/desk/build/build` would be a segment longer and no clearer, since `/desk/build`
		// already names both. Every workspace frappe ships is like this, so on a site with
		// nothing else installed the shell never appears on a workspace URL at all. It is with
		// erpnext and hrms that it starts to say something: 22 of 52 workspaces there are not
		// named after the shell they live in.
		cy.visit("/desk/build");
		cy.location("pathname").should("eq", "/desk/build");
		cy.get(".body-sidebar").should("have.attr", "data-title", "Build");
	});

	it("names the shell when the workspace is not named after it", () => {
		// The other half, which no frappe-only site can reach by navigating, so it is asked of the
		// function that builds the link. `Invoicing` under `Accounts` is the real shape of it.
		cy.window().then((win) => {
			const workspace = (shell) =>
				win.frappe.ui.sidebar_item.get_route(
					{ type: "Link", link_type: "Workspace", link_to: "Build" },
					false,
					shell
				);

			expect(workspace("Build")).to.eq("/desk/build");
			expect(workspace("Data")).to.eq("/desk/data/build");
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

	it("reads back a standard route it wrote a shell into", () => {
		// `/desk/List/DocType/List` is the spelling the desk used before friendly URLs. It still
		// honours one, so it must also be able to read back the URL it rewrites one into --
		// otherwise an old bookmark works once and breaks on the first reload.
		//
		// It broke because `segment_kind` knew workspaces, doctypes and pages but not view names,
		// so the shell went on and would not come off, and `build` was then read as the workspace
		// it also names.
		cy.visit("/desk/List/DocType/List");
		cy.location("pathname").should("eq", "/desk/build/List/DocType/List");
		cy.get(".list-count").should("exist");

		cy.reload();
		cy.get(".list-count").should("exist");
		cy.window().then((win) => {
			expect(win.frappe.get_route()).to.deep.eq(["List", "DocType", "List"]);
		});
	});

	it("does not re-route when handed the path already on screen", () => {
		// `set_route` is given ready-made paths as well as routes, and a path read off the page
		// carries the shell the desk wrote into it. Every relative link on the page is such a
		// path, `href=""` included.
		//
		// Left in, the shell makes `push_state` compare a path that has one against
		// `path_on_screen()`, which has none, so a link to the page you are on reads as a move
		// and re-renders it -- discarding whatever the render was holding. The form sidebar's
		// "Show All" was a casualty: it collapsed itself the moment it was clicked.
		cy.visit("/desk/build/todo");
		cy.get(".body-sidebar").should("have.attr", "data-title", "Build");

		cy.window().then((win) => {
			const router = win.frappe.router;
			let renders = 0;
			const render = router.render.bind(router);
			router.render = function () {
				renders += 1;
				return render();
			};

			// Exactly what the body-level link handler passes when a link on this page resolves
			// against the URL the desk has already written a shell into.
			return win.frappe.set_route(win.location.pathname).then(() => {
				expect(renders, "re-rendered the page it was already on").to.eq(0);
				expect(win.location.pathname).to.eq("/desk/build/todo");
				router.render = render;
			});
		});
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

	it("takes a stale shell off a workspace URL", () => {
		// `/desk/<other>/<workspace>` is a workspace under a shell that cannot show it. The shell
		// written in is the workspace's own, and when the workspace is named after that shell
		// `/desk/<workspace>` already says so, so nothing is added -- but the stale segment still
		// has to go, or it stays in the address bar and in every link copied from it.
		//
		// The pair is read off this site's payload rather than named, because which shell lists
		// which workspace is site data: on a site where no shell lists `Build`, there is no
		// workspace to be wrong about.
		cy.window().then((win) => {
			const router = win.frappe.router;
			const sidebars = win.frappe.boot.module_sidebars;
			const shell = Object.keys(sidebars).find((name) =>
				(sidebars[name].workspaces || []).some(
					(ws) =>
						router.shell_slug(name) === router.slug(ws) &&
						win.frappe.app.sidebar.module_for_workspace(ws) === name
				)
			);
			if (!shell) return; // no workspace here is named after the shell holding it

			const workspace = router.slug(
				sidebars[shell].workspaces.find(
					(ws) => router.slug(ws) === router.shell_slug(shell)
				)
			);
			const stale = Object.keys(sidebars)
				.map((name) => router.shell_slug(name))
				.find((slug) => slug !== workspace && slug !== "private");

			cy.visit(`/desk/${stale}/${workspace}`);
			cy.get(".body-sidebar").should("have.attr", "data-title", shell);
			cy.location("pathname").should("eq", `/desk/${workspace}`);
			cy.window().its("frappe.router.current_shell").should("eq", null);
		});
	});

	it("clears the highlight when nothing in the sidebar claims the route", () => {
		// Navigated in place rather than visited, because a fresh load rebuilds the sidebar and
		// would clear the highlight for the wrong reason. `User` stays in Build (same app) but
		// Build does not list it, so no item should be lit -- ToDo used to stay lit.
		cy.visit("/desk/build/todo");
		cy.get(".standard-sidebar-item.active-sidebar").should("have.length", 1);

		cy.window().then((win) => win.frappe.set_route("List", "User"));
		cy.location("pathname").should("eq", "/desk/build/user");
		cy.get(".body-sidebar").should("have.attr", "data-title", "Build");
		cy.get(".standard-sidebar-item.active-sidebar").should("have.length", 0);
	});

	it("matches a sidebar item only against the kind the route names", () => {
		// Names are not unique across kinds. A shell listing the Dashboard `User` does not list
		// the DocType `User`, and must not be taken as able to show it. No frappe-only site has
		// such a pair, so one is lent to the Build sidebar for the length of the test.
		cy.window().then((win) => {
			const sidebar = win.frappe.app.sidebar;
			const build = win.frappe.boot.module_sidebars["Build"];
			const items = build.items;
			build.items = [...items, { type: "Link", link_type: "Dashboard", link_to: "User" }];

			try {
				expect(sidebar.get_modules_linking("User", "Dashboard")).to.include("Build");
				expect(sidebar.get_modules_linking("User", "DocType")).not.to.include("Build");
				// Asked with no kind, any kind matches, as before.
				expect(sidebar.get_modules_linking("User")).to.include("Build");
			} finally {
				build.items = items;
			}
		});
	});

	it("opens the dock from the keyboard and hands focus back when it closes", () => {
		// The pointer at the window's edge used to be the only way in, and a closed dock is
		// inert, so a keyboard could never reach it. Driven through the method the shortcut
		// calls, since synthesising `shift+ctrl+/` depends on the keyboard layout.
		cy.visit("/desk/build/todo");
		cy.window().then((win) => {
			const dock = win.frappe.app.sidebar.dock;
			// A site whose app resolves to no dock entries draws no dock; nothing to test there.
			if (!dock?.enabled) return;

			expect(
				win.frappe.ui.keys.handlers["shift+ctrl+/"],
				"shortcut registered"
			).to.have.length.greaterThan(0);

			const opener = win.document.querySelector(".body-sidebar .item-anchor");
			opener.focus();

			dock.toggle_from_keyboard();
			expect(dock.is_open).to.eq(true);
			expect(dock.$dock[0].contains(win.document.activeElement), "focus in the dock").to.be
				.true;

			// A pointer nudge far from the edge must not shut it from under the keyboard.
			win.$(win.document).trigger(win.$.Event("mousemove", { clientX: 600, clientY: 300 }));
			expect(dock.is_open, "survives a pointer move").to.eq(true);

			win.$(win.document).trigger(win.$.Event("keydown", { key: "Escape" }));
			expect(dock.is_open).to.eq(false);
			expect(win.document.activeElement, "focus handed back").to.eq(opener);
		});
	});
});

function frappe_route(win, item, shell) {
	return win.frappe.ui.sidebar_item.get_route({ type: "Link", ...item }, false, shell);
}
