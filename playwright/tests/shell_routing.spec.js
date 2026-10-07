import { test, expect, TEST_USER } from "../support";

const pathname = (page) => new URL(page.url()).pathname;
const win_slug = (name) => name.toLowerCase().replace(/ /g, "-");
const SAVE_SIDEBAR =
	"frappe.desk.doctype.custom_sidebar.custom_sidebar.save_sidebar_customization";
const RESET_SIDEBAR = "frappe.desk.doctype.custom_sidebar.custom_sidebar.reset_user_sidebar";

async function open_desk(page, desk) {
	await page.goto("/desk/todo");
	await desk.ready();
}

async function expect_shell(page, shell) {
	await expect(page.locator(".body-sidebar")).toHaveAttribute("data-title", shell);
}

function current_module(page) {
	return page.evaluate(() => window.frappe?.app?.sidebar?.current_module);
}

function current_shell(page) {
	return page.evaluate(() => window.frappe?.router?.current_shell);
}

test.describe("Desk URL shell segment", () => {
	test("reads a shell off a route only when what follows names something", async ({
		page,
		desk,
	}) => {
		await open_desk(page, desk);
		const read = (segments) =>
			page.evaluate((segments) => {
				const router = frappe.router;
				return [router.take_shell_from(segments.slice()), router.current_shell];
			}, segments);

		expect(await read(["build", "todo"])).toEqual([["todo"], "Build"]);
		expect(await read(["build", "todo", "TODO-0001"])).toEqual([
			["todo", "TODO-0001"],
			"Build",
		]);
		expect(await read(["build", "todo", "view", "report"])).toEqual([
			["todo", "view", "report"],
			"Build",
		]);

		expect(await read(["todo", "TODO-0001"])).toEqual([["todo", "TODO-0001"], null]);

		expect(await read(["workflow", "WF-0001"])).toEqual([["workflow", "WF-0001"], null]);
		expect(await read(["workflow", "todo"])).toEqual([["workflow", "todo"], null]);

		expect(await read(["build"])).toEqual([["build"], null]);

		expect(await read(["not-a-shell", "todo"])).toEqual([["not-a-shell", "todo"], null]);

		expect(await read(["build", "query-report", "Permitted Documents For User"])).toEqual([
			["query-report", "Permitted Documents For User"],
			"Build",
		]);
	});

	test("never strips a leading `private` as a shell prefix", async ({ page, desk }) => {
		await open_desk(page, desk);
		const result = await page.evaluate(() => {
			const router = frappe.router;
			const shells = frappe.boot.module_sidebars;
			const before = shells["Private"];
			shells["Private"] = { name: "Private", module: "Private", items: [] };
			router.setup_shell_routes();

			const result = {
				has_private_route: "private" in router.shell_routes,
				taken: router.take_shell_from(["private", "todo"]),
				current_shell: router.current_shell,
			};

			if (before) shells["Private"] = before;
			else delete shells["Private"];
			router.setup_shell_routes();
			return result;
		});

		expect(result.has_private_route).toBe(false);
		expect(result.taken).toEqual(["private", "todo"]);
		expect(result.current_shell).toBe(null);
	});

	test("opens a private page in the Private shell, and keeps it in a module that lists it", async ({
		page,
		desk,
		api,
	}) => {
		await open_desk(page, desk);
		const module = await page.evaluate(() => frappe.boot.module_sidebars["Build"].module);
		const name = `Test Private Page-${TEST_USER}`;

		await api.remove_doc("Workspace", name, true);
		await api.call("frappe.client.insert", {
			doc: {
				doctype: "Workspace",
				title: "Test Private Page",
				label: name,
				module,
				public: 0,
				for_user: TEST_USER,
				content: "[]",
			},
		});

		try {
			await page.goto("/desk/private");
			await expect.poll(() => pathname(page)).toBe("/desk/private/test-private-page");
			await expect.poll(() => current_module(page)).toBe("Private");

			await page.goto(`/desk/private/${win_slug(name)}`);
			await expect.poll(() => pathname(page)).toBe("/desk/private/test-private-page");

			await page.goto("/desk/build/private/test-private-page");
			await expect.poll(() => pathname(page)).toBe("/desk/build/private/test-private-page");
			await expect.poll(() => current_module(page)).toBe("Build");
		} finally {
			await api.call("frappe.client.delete", { doctype: "Workspace", name });
		}
	});

	test("opens the Private shell on the first item of its sidebar, page or not", async ({
		page,
		api,
	}) => {
		const name = `Test Landing Page-${TEST_USER}`;

		await api.remove_doc("Workspace", name, true);
		await api.call("frappe.client.insert", {
			doc: {
				doctype: "Workspace",
				title: "Test Landing Page",
				label: name,
				module: "Private",
				public: 0,
				for_user: TEST_USER,
				content: "[]",
			},
		});

		try {
			await api.call(SAVE_SIDEBAR, {
				module: "Private",
				items: JSON.stringify([
					{
						added: 1,
						type: "Link",
						link_type: "DocType",
						link_to: "ToDo",
						label: "My ToDos",
					},
					{
						added: 1,
						type: "Link",
						link_type: "Workspace",
						link_to: name,
						label: "Test Landing Page",
					},
				]),
			});

			await page.goto("/desk/private");
			await expect.poll(() => pathname(page)).toBe("/desk/private/todo");
			await expect.poll(() => current_module(page)).toBe("Private");
		} finally {
			await api.call(RESET_SIDEBAR, { module: "Private" });
			await api.call("frappe.client.delete", { doctype: "Workspace", name });
		}
	});

	test("opens a landing that leaves the desk in a tab, and draws the pane", async ({
		page,
		desk,
		api,
	}) => {
		await api.call(SAVE_SIDEBAR, {
			module: "Private",
			items: JSON.stringify([
				{
					added: 1,
					type: "Link",
					link_type: "URL",
					url: "https://frappe.io/",
					label: "Frappe",
				},
			]),
		});

		try {
			await open_desk(page, desk);
			await page.evaluate(() => {
				window.opened_tabs = [];
				window.open = (...args) => {
					window.opened_tabs.push(args);
				};
				frappe.set_route("private");
			});

			await expect
				.poll(() => page.evaluate(() => window.opened_tabs))
				.toContainEqual(["https://frappe.io/", "_blank", "noopener"]);
			await expect.poll(() => pathname(page)).toBe("/desk/private");
			await expect(page.locator(".private-shell-empty")).not.toHaveCount(0);
		} finally {
			await api.call(RESET_SIDEBAR, { module: "Private" });
		}
	});

	test("reads anything else after `private` as a route inside the Private shell", async ({
		page,
		desk,
	}) => {
		await page.goto("/desk/private/todo");
		await expect.poll(() => pathname(page)).toBe("/desk/private/todo");
		await expect.poll(() => current_module(page)).toBe("Private");
		await expect
			.poll(() => page.evaluate(() => frappe.router.current_route))
			.toEqual(["List", "ToDo", "List"]);

		await page.goto("/desk/private/no-such-page-of-mine");
		await expect(desk.get_open_dialog()).toContainText("does not exist");
		await desk.hide_dialog();
	});

	test("spells an ampersand out rather than encoding it", async ({ page, desk }) => {
		await open_desk(page, desk);
		const slugs = await page.evaluate(() => [
			frappe.router.shell_slug("Shift & Attendance"),
			frappe.router.shell_slug("Build"),
		]);
		expect(slugs).toEqual(["shift-and-attendance", "build"]);
	});

	test("honours a shell only when it can show what the route names", async ({ page, desk }) => {
		await open_desk(page, desk);
		const shell_from_url = (shell) =>
			page.evaluate((shell) => {
				const router = frappe.router;
				router.current_shell = shell;
				const answer = frappe.app.sidebar.shell_from_url(["List", "ToDo", "List"]);
				router.current_shell = null;
				return answer;
			}, shell);

		expect(await shell_from_url("Build")).toBe("Build");
		expect(await shell_from_url("Users")).toBe("Users");
		expect(await shell_from_url("Not A Real Shell")).toBe(null);
	});

	test("shows the shell the URL names", async ({ page }) => {
		await page.goto("/desk/build/todo");
		await expect_shell(page, "Build");
	});

	test("keeps a shell that does not list the entity but belongs to its app", async ({
		page,
	}) => {
		await page.goto("/desk/build/user");
		await expect_shell(page, "Build");
	});

	test("writes the shell into a URL that arrived without one", async ({ page }) => {
		await page.goto("/desk/todo");
		await expect.poll(() => pathname(page)).toBe("/desk/build/todo");
	});

	test("leaves the query string and the fragment alone while doing it", async ({ page }) => {
		await page.goto("/desk/todo?status=Open");
		await expect.poll(() => pathname(page)).toBe("/desk/build/todo");
		await expect.poll(() => new URL(page.url()).search).toBe("?status=Open");
	});

	test("keeps the shell you are standing in as you navigate", async ({ page }) => {
		await page.goto("/desk/users/user");
		// The sidebar itself, not just the URL: the URL is correct a moment before the sidebar
		// has read it.
		await expect_shell(page, "Users");

		// Without the third argument, since `set_route("List", "ToDo", "List")` asks for the list
		// view by name and writes `/desk/todo/view/list`.
		await page.evaluate(() => frappe.set_route("List", "ToDo"));
		await expect.poll(() => pathname(page)).toBe("/desk/users/todo");
		await expect_shell(page, "Users");
	});

	test("moves into the shell a link names, from a page with no shell", async ({ page }) => {
		// What a desktop icon does: it opens its module on the first link, spelled with the
		// module's shell. ToDo opens in Build when nothing names one, so dropping the shell from
		// the link would land it there instead of in the module the icon stands for.
		await page.goto("/desk/desktop");
		await page.evaluate(() => {
			const link = document.createElement("a");
			link.href = "/desk/users/todo";
			link.textContent = "ToDo in Users";
			document.body.appendChild(link);
			link.click();
		});
		await expect.poll(() => pathname(page)).toBe("/desk/users/todo");
		await expect_shell(page, "Users");
	});

	test("does not rewrite history when you go back", async ({ page }) => {
		await page.goto("/desk/build/todo");
		await page.goto("/desk/users/user");
		await page.goBack();

		await expect.poll(() => pathname(page)).toBe("/desk/build/todo");
		await expect_shell(page, "Build");
	});

	test("opens a report through a shell", async ({ page }) => {
		await page.goto("/desk/build/query-report/Permitted%20Documents%20For%20User");
		await expect
			.poll(() => pathname(page))
			.toMatch(/\/query-report\/Permitted%20Documents%20For%20User$/);
		await expect
			.poll(() => page.evaluate(() => window.frappe?.get_route?.()))
			.toEqual(["query-report", "Permitted Documents For User"]);
	});

	test("leaves a workspace alone when it is named after its own shell", async ({ page }) => {
		await page.goto("/desk/build");
		await expect.poll(() => pathname(page)).toBe("/desk/build");
		await expect_shell(page, "Build");
	});

	test("names the shell when the workspace is not named after it", async ({ page, desk }) => {
		await open_desk(page, desk);
		const workspace = (shell) =>
			page.evaluate(
				(shell) =>
					frappe.ui.sidebar_item.get_route(
						{ type: "Link", link_type: "Workspace", link_to: "Build" },
						false,
						shell
					),
				shell
			);

		expect(await workspace("Build")).toBe("/desk/build");
		expect(await workspace("Data")).toBe("/desk/data/build");
	});

	test("highlights the sidebar item you are looking at", async ({ page }) => {
		await page.goto("/desk/build/todo");
		await expect_shell(page, "Build");
		await expect(page.locator(".standard-sidebar-item.active-sidebar")).toHaveCount(1);
	});

	test("reads back a standard route it wrote a shell into", async ({ page }) => {
		await page.goto("/desk/List/DocType/List");
		await expect.poll(() => pathname(page)).toBe("/desk/build/List/DocType/List");
		await expect(page.locator(".list-count")).not.toHaveCount(0);

		await page.reload();
		await expect(page.locator(".list-count")).not.toHaveCount(0);
		expect(await page.evaluate(() => frappe.get_route())).toEqual(["List", "DocType", "List"]);
	});

	test("does not re-route when handed the path already on screen", async ({ page }) => {
		await page.goto("/desk/build/todo");
		await expect_shell(page, "Build");

		const result = await page.evaluate(async () => {
			const router = frappe.router;
			let renders = 0;
			const render = router.render.bind(router);
			router.render = function () {
				renders += 1;
				return render();
			};

			await frappe.set_route(window.location.pathname);
			router.render = render;
			return { renders, pathname: window.location.pathname };
		});

		expect(result.renders, "re-rendered the page it was already on").toBe(0);
		expect(result.pathname).toBe("/desk/build/todo");
	});

	test("builds sidebar links that already name their shell", async ({ page }) => {
		await page.goto("/desk/build/todo");
		await expect_shell(page, "Build");

		const frappe_route = (item, shell) =>
			page.evaluate(
				([item, shell]) =>
					frappe.ui.sidebar_item.get_route({ type: "Link", ...item }, false, shell),
				[item, shell]
			);

		expect(await frappe_route({ link_type: "DocType", link_to: "ToDo" }, "Build")).toBe(
			"/desk/build/todo"
		);
		expect(await frappe_route({ link_type: "URL", url: "https://frappe.io" }, "Build")).toBe(
			"https://frappe.io"
		);
	});

	test("opens a report link with its filters", async ({ page }) => {
		// Stock Balance for one warehouse is a link of its own: v16 kept the warehouse in route
		// options, the conversion stores it as filters, and the report reads it off the query string.
		await page.goto("/desk/build/todo");
		await expect_shell(page, "Build");

		const route = await page.evaluate(() =>
			frappe.ui.sidebar_item.get_route(
				{
					type: "Link",
					link_type: "Report",
					link_to: "Permitted Documents For User",
					report: { report_type: "Script Report", ref_doctype: "User" },
					filters: JSON.stringify([
						["Permitted Documents For User", "user", "=", "test@example.com"],
					]),
				},
				false,
				"Build"
			)
		);
		expect(route).toBe(
			"/desk/build/query-report/Permitted Documents For User?user=test%40example.com"
		);
	});

	test("takes a stale shell off a workspace URL", async ({ page, desk }) => {
		await open_desk(page, desk);
		// The pair is read off this site's payload rather than named, because which shell lists
		// which workspace is site data.
		const pair = await page.evaluate(() => {
			const router = frappe.router;
			const sidebars = frappe.boot.module_sidebars;
			const shell = Object.keys(sidebars).find((name) =>
				(sidebars[name].workspaces || []).some(
					(ws) =>
						router.shell_slug(name) === router.slug(ws) &&
						frappe.app.sidebar.module_for_workspace(ws) === name
				)
			);
			if (!shell) return null;

			const workspace = router.slug(
				sidebars[shell].workspaces.find(
					(ws) => router.slug(ws) === router.shell_slug(shell)
				)
			);
			const stale = Object.keys(sidebars)
				.map((name) => router.shell_slug(name))
				.find((slug) => slug !== workspace && slug !== "private");
			return { shell, workspace, stale };
		});
		if (!pair) return;

		await page.goto(`/desk/${pair.stale}/${pair.workspace}`);
		await expect_shell(page, pair.shell);
		await expect.poll(() => pathname(page)).toBe(`/desk/${pair.workspace}`);
		await expect.poll(() => page.evaluate(() => frappe.router.current_shell)).toBe(null);
	});

	test("clears the highlight when nothing in the sidebar claims the route", async ({ page }) => {
		// Navigated in place rather than visited, because a fresh load rebuilds the sidebar and
		// would clear the highlight for the wrong reason.
		const active_item = page.locator(".standard-sidebar-item.active-sidebar");
		await page.goto("/desk/build/todo");
		await expect(active_item).toHaveCount(1);

		await page.evaluate(() => frappe.set_route("List", "User"));
		await expect.poll(() => pathname(page)).toBe("/desk/build/user");
		await expect_shell(page, "Build");
		await expect(active_item).toHaveCount(0);
	});

	test("matches a sidebar item only against the kind the route names", async ({
		page,
		desk,
	}) => {
		await open_desk(page, desk);
		const linking = await page.evaluate(() => {
			const sidebar = frappe.app.sidebar;
			const build = frappe.boot.module_sidebars["Build"];
			const items = build.items;
			build.items = [...items, { type: "Link", link_type: "Dashboard", link_to: "User" }];

			try {
				return {
					dashboard: sidebar.get_modules_linking("User", "Dashboard"),
					doctype: sidebar.get_modules_linking("User", "DocType"),
					any: sidebar.get_modules_linking("User"),
				};
			} finally {
				build.items = items;
			}
		});

		expect(linking.dashboard).toContain("Build");
		expect(linking.doctype).not.toContain("Build");
		expect(linking.any).toContain("Build");
	});

	test("opens the dock from the keyboard and hands focus back when it closes", async ({
		page,
		desk,
	}) => {
		await page.goto("/desk/build/todo");
		await desk.ready();

		// Driven through the method the shortcut calls, since synthesising `shift+ctrl+/`
		// depends on the keyboard layout.
		const result = await page.evaluate(() => {
			const dock = frappe.app.sidebar.dock;
			if (!dock?.enabled) return null;
			// only a floating dock is summoned and dismissed; a pinned one stays open
			dock.set_pinned(false);

			const result = {
				shortcut_handlers: (frappe.ui.keys.handlers["shift+ctrl+/"] || []).length,
			};

			const opener = document.querySelector(".body-sidebar .item-anchor[href]");
			opener.focus();

			dock.toggle_from_keyboard();
			result.opened = dock.is_open;
			result.focus_in_dock = dock.$dock[0].contains(document.activeElement);

			$(document).trigger($.Event("mousemove", { clientX: 600, clientY: 300 }));
			result.open_after_pointer_move = dock.is_open;

			$(document).trigger($.Event("keydown", { key: "Escape" }));
			result.open_after_escape = dock.is_open;
			result.focus_handed_back = document.activeElement === opener;
			return result;
		});
		if (!result) return;

		expect(result.shortcut_handlers, "shortcut registered").toBeGreaterThan(0);
		expect(result.opened).toBe(true);
		expect(result.focus_in_dock, "focus in the dock").toBe(true);
		expect(result.open_after_pointer_move, "survives a pointer move").toBe(true);
		expect(result.open_after_escape).toBe(false);
		expect(result.focus_handed_back, "focus handed back").toBe(true);
	});
});
