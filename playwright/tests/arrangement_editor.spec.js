import { test, expect } from "../support";

const ENTRIES = [
	{ key: "alpha", label: "Alpha" },
	{ key: "beta", label: "Beta" },
	{ key: "gamma", label: "Gamma" },
];

const with_class = (name) => new RegExp(`(^|\\s)${name}(\\s|$)`);

// The sidebar settles on the route's shell a moment after the desk is ready. An editor opened
// before that would see the settling as the desk moving elsewhere, and leave.
async function open_desk(page, desk) {
	await page.goto("/desk/todo");
	await desk.ready();
	await page.evaluate(async () => {
		await frappe.require("arrangement_editor.bundle.js");
	});
	await page.waitForFunction(() => {
		const sidebar = frappe.app.sidebar;
		return sidebar.current_module === sidebar.shell_for_current_route(frappe.get_route());
	});
}

// The desk keeps calling the server while the editor is open, and those calls land on the stub
// too, so the endpoints a test answers are recorded by name and told apart from the rest.
async function stub_xcall(page, responses, failures = {}) {
	await page.evaluate(
		([responses, failures]) => {
			const calls = [];
			frappe.xcall = (method, args) => {
				calls.push({ method, args });
				if (method in failures) {
					return Promise.reject(new Error(failures[method]));
				}
				return Promise.resolve(
					method in responses ? structuredClone(responses[method]) : {}
				);
			};
			window.__calls = calls;
			window.__stubbed = new Set([...Object.keys(responses), ...Object.keys(failures)]);
		},
		[responses, failures]
	);
}

function stubbed_calls(page) {
	return page.evaluate(() =>
		window.__calls.map((call) => call.method).filter((method) => window.__stubbed.has(method))
	);
}

function saved_args(page, method) {
	return page.evaluate(
		(method) => window.__calls.find((call) => call.method === method)?.args ?? null,
		method
	);
}

async function saved_rows(page, method) {
	await expect.poll(() => saved_args(page, method)).not.toBeNull();
	return JSON.parse((await saved_args(page, method)).items);
}

// Somebody who may write only their own layer, so an editor opens on the one layer a test stubs.
// Whether the account running the tests may curate for everyone, and whether the site is in
// developer mode and so offers the app's layer, are facts about the site.
async function as_plain_user(page) {
	await page.evaluate(() => {
		const has_role = frappe.user.has_role.bind(frappe.user);
		frappe.user.has_role = (role) => (role === "Workspace Manager" ? false : has_role(role));
		frappe.boot.developer_mode = 0;
	});
}

async function open_editor(page, { hidden = [], can_curate = false, note = "" } = {}) {
	await page.evaluate(
		([hidden, can_curate, note]) => {
			class TestSurface extends frappe.ui.ArrangementEditor {
				prepare() {
					this.can_curate_site = can_curate;
				}

				get layers() {
					return {
						user: {
							read: "read.user",
							save: "save.user",
							label: () => "Just for me",
							phrase: () => "just for me",
							saved: () => "Saved",
						},
						site: {
							read: "read.site",
							save: "save.site",
							label: () => "For everyone",
							phrase: () => "for everyone",
							condition: () => this.can_curate_site,
							saved: () => "Saved for everyone",
						},
					};
				}

				title() {
					return "the test surface";
				}

				// It arranges nothing on the desk, so no navigation takes it away.
				survives_shell() {
					return true;
				}

				pane_note() {
					return note;
				}

				async read() {
					const rows = await frappe.xcall(this.layer_config.read);
					this.entries = new Map(rows.map((row) => [row.key, { ...row }]));
					this.arrange(
						rows.map((row) => row.key),
						hidden
					);
				}

				save_args() {
					return {
						items: this.arranged_rows((key, is_hidden) => ({
							key,
							hidden: is_hidden,
						})),
					};
				}

				apply() {}

				reset() {
					this.hidden = new Set(this.all_keys());
					this.render_list();
				}

				copy() {
					return {
						add_label: "Add",
						list_empty: "Nothing to arrange",
						load_error: "Could not load the arrangement.",
					};
				}
			}

			window.__editor = new TestSurface();
		},
		[hidden, can_curate, note]
	);
}

function foot_button(page, label) {
	return page.locator(".sidebar-editor .ws-foot").getByRole("button", { name: label });
}

// The values are set on the panel's field group rather than typed: a field group redraws its
// dependencies a moment after any field changes, and a keystroke that lands in that redraw is
// lost. What is under test is where the entry lands, not the controls.
async function add_through_panel(page, values) {
	await page.locator(".ws-add-row").click();
	await expect(page.locator(".ws-panel")).toBeVisible();
	await page.evaluate((values) => window.__editor.panel.field_group.set_values(values), values);
	await page.locator(".ws-panel .ws-panel-foot").getByRole("button", { name: "Add" }).click();
	await expect(page.locator(".ws-panel")).toHaveCount(0);
}

function row_control(page, index, control) {
	return page.locator(".ws-row").nth(index).locator(control);
}

test.describe("Arrangement editor", () => {
	test.beforeEach(async ({ page, desk }) => {
		await open_desk(page, desk);
	});

	test("draws in the sidebar's own column, holding every entry", async ({ page }) => {
		await stub_xcall(page, { "read.user": ENTRIES });
		await open_editor(page);

		await expect(page.locator(".body-sidebar-container")).toHaveClass(
			with_class("sidebar-editing")
		);
		await expect(page.locator(".body-sidebar .sidebar-editor")).toBeVisible();
		await expect(page.locator(".body-sidebar .sidebar-header")).toBeVisible();
		await expect(page.locator(".body-sidebar .sidebar-items")).toBeHidden();
		await expect(page.locator(".ws-row")).toHaveCount(3);
		await expect(page.locator(".ws-row .ws-row-label").first()).toHaveText("Alpha");
		await expect(page.locator(".modal:visible")).toHaveCount(0);
	});

	test("keeps an entry the eye has off in the list, in its place", async ({ page }) => {
		await stub_xcall(page, { "read.user": ENTRIES });
		await open_editor(page, { hidden: ["beta"] });

		const rows = page.locator(".ws-row");
		await expect(rows).toHaveCount(3);
		await expect(rows.nth(1)).toHaveClass(with_class("is-hidden"));
		await expect(rows.nth(1).locator(".ws-row-label")).toHaveText("Beta");
	});

	test("takes an entry off with the eye, and only offers Save once something changed", async ({
		page,
	}) => {
		await stub_xcall(page, { "read.user": ENTRIES });
		await open_editor(page);

		const save = foot_button(page, "Save");
		await expect(save).toBeDisabled();
		await row_control(page, 1, ".ws-eye").click({ force: true });
		await expect(page.locator(".ws-row").nth(1)).toHaveClass(with_class("is-hidden"));
		await expect(save).toBeEnabled();

		// And back on, into the place it never left, which is no change at all.
		await row_control(page, 1, ".ws-eye").click({ force: true });
		await expect(page.locator(".ws-row").nth(1)).not.toHaveClass(with_class("is-hidden"));
		await expect(save).toBeDisabled();
	});

	test("saves the whole arrangement, in order, and gives the column back", async ({ page }) => {
		await stub_xcall(page, { "read.user": ENTRIES, "save.user": {} });
		await open_editor(page);

		await row_control(page, 0, ".ws-eye").click({ force: true });
		await foot_button(page, "Save").click();

		// An entry left out would keep whatever the layer below said about it, so every entry
		// goes back, carrying its own flag.
		await expect
			.poll(async () => (await saved_args(page, "save.user"))?.items)
			.toEqual([
				{ key: "alpha", hidden: 1 },
				{ key: "beta", hidden: 0 },
				{ key: "gamma", hidden: 0 },
			]);
		await expect(page.locator(".sidebar-editor")).toHaveCount(0);
		await expect(page.locator(".body-sidebar-container")).not.toHaveClass(
			with_class("sidebar-editing")
		);
	});

	test("opens a curator on the site's layer, and reads the other layer on a switch", async ({
		page,
	}) => {
		await stub_xcall(page, { "read.user": ENTRIES, "read.site": ENTRIES });
		await open_editor(page, { can_curate: true });

		// Arranging for everyone is what the permission is for, so that is the layer it opens on.
		// The phrase after the module's name opens the layers; the rest of the header opens nothing.
		const phrase = page.locator(".sidebar-header .ws-layer-phrase");
		await expect(phrase).toHaveText("for everyone");
		await page.locator(".sidebar-header .header-title").click({ force: true });
		await expect(page.locator(".es-menu")).toHaveCount(0);
		await page.locator(".sidebar-header .ws-layer-switch").click();
		await page.locator('.es-menu [role="menuitem"]', { hasText: "Just for me" }).click();

		// The other layer is a different arrangement, so it is read rather than filtered.
		await expect(phrase).toHaveText("just for me");
		await expect(page.locator(".ws-row")).toHaveCount(3);
		await expect.poll(() => stubbed_calls(page)).toEqual(["read.site", "read.user"]);
	});

	test("tells what the layer note says on the layer switch, not in the column", async ({
		page,
	}) => {
		await stub_xcall(page, { "read.user": ENTRIES });
		await open_editor(page, { note: "Something sits on top of this layer." });

		await expect(page.locator(".ws-row")).toHaveCount(3);
		await expect(page.locator(".ws-note")).toHaveCount(0);
		await page.locator(".sidebar-header .ws-layer-switch").hover();
		await expect(page.locator(".es-tooltip")).toHaveText(
			"Something sits on top of this layer."
		);
	});

	test("offers no layer switch to somebody who may not curate for everyone", async ({
		page,
	}) => {
		await stub_xcall(page, { "read.user": ENTRIES });
		await open_editor(page);

		await expect(page.locator(".ws-row")).toHaveCount(3);
		await expect(page.locator(".sidebar-header .ws-layer-phrase")).toHaveText("just for me");
		await expect(page.locator(".sidebar-header .ws-layer-switch svg")).toHaveCount(0);
		expect(await stubbed_calls(page)).toEqual(["read.user"]);
	});

	test("says a read failed instead of sitting on Loading, and will not save what it never read", async ({
		page,
	}) => {
		await stub_xcall(page, { "save.user": {} }, { "read.user": "no arrangement for you" });
		await open_editor(page);

		await expect(page.locator(".sidebar-editor")).toContainText(
			"Could not load the arrangement."
		);
		await expect(foot_button(page, "Save")).toBeDisabled();
		expect(await page.evaluate(() => window.__editor.save())).toBe(false);
		expect(await saved_args(page, "save.user")).toBeNull();
	});

	test("asks before Cancel throws changes away, and closes at once when there are none", async ({
		page,
	}) => {
		await stub_xcall(page, { "read.user": ENTRIES });
		await open_editor(page);

		await row_control(page, 0, ".ws-eye").click({ force: true });
		await foot_button(page, "Cancel").click();
		const confirm = page.locator(".modal:visible", { hasText: "Discard your changes?" });
		await expect(confirm).toBeVisible();
		await confirm.getByRole("button", { name: "Yes" }).click();
		await expect(page.locator(".sidebar-editor")).toHaveCount(0);

		await expect(page.locator(".modal:visible")).toHaveCount(0);
		await open_editor(page);
		await expect(page.locator(".ws-row")).toHaveCount(3);
		await foot_button(page, "Cancel").click();
		await expect(page.locator(".sidebar-editor")).toHaveCount(0);
	});
});

test.describe("Arrangement editor: a module's sidebar", () => {
	// What the read endpoint returns: the layer as it arranges the sidebar, with hidden entries
	// kept. A section and one member of it, so both things a sidebar has and the dock does not are
	// on screen.
	const ITEMS = [
		{
			key: "Link|DocType|ToDo|",
			type: "Link",
			link_type: "DocType",
			link_to: "ToDo",
			label: "To Do",
			hidden: 0,
			child: 0,
		},
		{ key: "sec-records", type: "Section Break", label: "Records", hidden: 0, child: 0 },
		{
			key: "Link|DocType|Note|",
			type: "Link",
			link_type: "DocType",
			link_to: "Note",
			label: "Note",
			hidden: 0,
			child: 1,
		},
	];

	const READ = "frappe.desk.doctype.custom_sidebar.custom_sidebar.get_user_sidebar_layer";
	const SAVE = "frappe.desk.doctype.custom_sidebar.custom_sidebar.save_sidebar_customization";

	let module_sidebars;
	let other_module;

	// Opens the real editor on the sidebar on screen, with only `responses` answering.
	async function open_sidebar_editor(page, responses) {
		await stub_xcall(page, responses);
		await page.evaluate(() => {
			window.__editor?.close();
			window.__editor = new frappe.ui.SidebarManager();
		});
	}

	test.beforeEach(async ({ page, desk }) => {
		await open_desk(page, desk);
		await as_plain_user(page);

		module_sidebars = await page.evaluate(() => frappe.boot.module_sidebars);
		other_module = await page.evaluate(() =>
			Object.keys(frappe.boot.module_sidebars).find(
				(module) => module !== frappe.app.sidebar.current_module
			)
		);
		await open_sidebar_editor(page, { [READ]: ITEMS, [SAVE]: { module_sidebars } });
	});

	test("keeps the first row where the sidebar draws its first link", async ({ page }) => {
		await page.evaluate(() => window.__editor.close());
		const live = await page.locator(".sidebar-items .item-anchor").first().boundingBox();
		await open_sidebar_editor(page, { [READ]: ITEMS, [SAVE]: { module_sidebars } });

		const editing = await page.locator(".ws-row").first().boundingBox();
		expect(Math.abs(editing.y - live.y)).toBeLessThanOrEqual(1);
	});

	test("draws each entry the way the sidebar draws it", async ({ page }) => {
		const rows = page.locator(".ws-row");
		await expect(rows).toHaveCount(3);
		// A section is the sidebar's own section markup, drawn as a heading.
		await expect(rows.nth(1)).toHaveClass(with_class("ws-row-heading"));
		await expect(rows.nth(1).locator(".section-break")).toContainText("Records");
		// A link carries no route here, so nothing in the list navigates.
		await expect(rows.nth(0).locator(".item-anchor")).not.toHaveAttribute("href", /.*/);
	});

	test("adds a section, and then puts what is added next into it", async ({ page }) => {
		await add_through_panel(page, { kind: "Section", label: "Mine" });
		await expect(page.locator(".ws-row")).toHaveCount(4);
		await expect(page.locator(".ws-row").last()).toHaveClass(with_class("ws-row-heading"));

		// A URL rather than a document link: what is under test is where the entry lands, and a
		// Dynamic Link would bring a search box into a test that is not about one.
		await add_through_panel(page, {
			kind: "Link",
			link_type: "URL",
			url: "https://example.com",
			label: "Elsewhere",
		});

		// The entry added after it lands under it, which is what puts it in the section.
		await expect(page.locator(".ws-row")).toHaveCount(5);
		const child = await page.evaluate(
			() =>
				[...window.__editor.entries.values()].find((entry) => entry.label === "Elsewhere")
					.child
		);
		expect(child).toBe(1);
	});

	test("picks the kind of entry with pills, and flags what Add is missing only when pressed", async ({
		page,
	}) => {
		await page.locator(".ws-add-row").click();
		await expect(page.locator(".ws-panel .has-error")).toHaveCount(0);

		// A section needs only a label, so the fields a link needs go away.
		await page.locator(".ws-panel-choice").getByRole("radio", { name: "Section" }).click();
		await expect(
			page.locator(".ws-panel .frappe-control[data-fieldname='link_type']")
		).toBeHidden();

		await page
			.locator(".ws-panel .ws-panel-foot")
			.getByRole("button", { name: "Add" })
			.click();
		await expect(page.locator(".ws-panel [data-fieldname='label']").first()).toHaveClass(
			with_class("has-error")
		);
		await expect(page.locator(".ws-row")).toHaveCount(3);
	});

	test("removes an entry this layer added rather than hiding it", async ({ page }) => {
		await add_through_panel(page, { kind: "Section", label: "Mine" });

		// Nothing below holds it, so there is no hiding it: it carries a cross, not an eye.
		const last = page.locator(".ws-row").last();
		await expect(last.locator(".ws-eye")).toHaveCount(0);
		await last.locator(".ws-remove").click({ force: true });
		await expect(page.locator(".ws-row")).toHaveCount(3);
	});

	test("sends an added section without a key, for the server to name", async ({ page }) => {
		await add_through_panel(page, { kind: "Section", label: "Mine" });
		await foot_button(page, "Save").click();

		const added = (await saved_rows(page, SAVE)).find((row) => row.added);
		expect(added.type).toBe("Section Break");
		expect(added.label).toBe("Mine");
		// A row that leads nowhere is named by a hash of its type and label, and the server
		// computes that.
		expect(added.key).toBeNull();
	});

	test("opens an entry's fields beside the column and applies a relabel as it is typed", async ({
		page,
	}) => {
		await page.locator(".ws-row").first().click();
		await expect(page.locator(".ws-row").first()).toHaveClass(with_class("is-open"));
		const panel = page.locator(".ws-panel");
		await expect(panel).toBeVisible();
		await expect(panel).toContainText("Edit Link");

		// Beside the column, not over it.
		const column = await page.locator(".body-sidebar").boundingBox();
		const box = await panel.boundingBox();
		expect(box.x).toBeGreaterThan(column.x + column.width);

		const label = panel.locator("[data-fieldname='label'] input");
		await label.fill("My Tasks");
		await expect(page.locator(".ws-row").first().locator(".sidebar-item-label")).toHaveText(
			"My Tasks"
		);
		await expect(foot_button(page, "Save")).toBeEnabled();

		// Esc closes the panel and nothing else.
		await page.keyboard.press("Escape");
		await expect(panel).toHaveCount(0);
		await expect(page.locator(".sidebar-editor")).toHaveCount(1);
	});

	test("takes a row off your own sidebar with the cross, which leaves the list and saves it hidden", async ({
		page,
	}) => {
		await expect(page.locator(".sidebar-header .ws-layer-phrase")).toHaveText("just for me");
		await expect(page.locator(".ws-row .ws-eye")).toHaveCount(0);
		await row_control(page, 0, ".ws-remove").click({ force: true });
		await expect(page.locator(".ws-row")).toHaveCount(2);

		await foot_button(page, "Save").click();
		const rows = await saved_rows(page, SAVE);
		expect(rows).toHaveLength(3);
		expect(rows.find((row) => row.link_to === "ToDo").hidden).toBe(1);
	});

	test("takes a row off for everyone with the cross, which leaves the list and saves it hidden", async ({
		page,
	}) => {
		const SITE_READ =
			"frappe.desk.doctype.custom_sidebar.custom_sidebar.get_site_sidebar_layer";
		const SITE_SAVE = "frappe.desk.doctype.custom_sidebar.custom_sidebar.save_site_sidebar";
		// Reopened as a curator, which is who the site's layer opens for.
		await page.evaluate(() => {
			frappe.user.has_role = () => true;
		});
		await open_sidebar_editor(page, { [SITE_READ]: ITEMS, [SITE_SAVE]: { module_sidebars } });

		await expect(page.locator(".sidebar-header .ws-layer-phrase")).toHaveText("for everyone");
		await expect(row_control(page, 0, ".ws-eye")).toHaveCount(0);
		await row_control(page, 0, ".ws-remove").click({ force: true });
		await expect(page.locator(".ws-row")).toHaveCount(2);

		await foot_button(page, "Save").click();
		// Still the whole arrangement: the row goes back hidden.
		const rows = await saved_rows(page, SITE_SAVE);
		expect(rows).toHaveLength(3);
		expect(rows.find((row) => row.link_to === "ToDo").hidden).toBe(1);
	});

	test("deletes a row from what the app ships with the cross", async ({ page }) => {
		const APP_READ = "frappe.desk.doctype.sidebar.sidebar.get_app_sidebar_layer";
		const APP_SAVE = "frappe.desk.doctype.sidebar.sidebar.save_app_sidebar";
		// Reopened in developer mode, which is where the app's layer is offered.
		await page.evaluate(() => {
			frappe.boot.developer_mode = 1;
		});
		await open_sidebar_editor(page, { [APP_READ]: ITEMS, [APP_SAVE]: { module_sidebars } });

		await expect(page.locator(".ws-row .ws-eye")).toHaveCount(0);

		// The app's layer holds the section itself, so its panel says how it draws.
		await page.locator(".ws-row").nth(1).click();
		const panel = page.locator(".ws-panel");
		await expect(panel).toContainText("Edit Section");
		await expect(panel.locator(".frappe-control[data-fieldname='indent']")).toBeVisible();
		await expect(panel.locator(".frappe-control[data-fieldname='collapsible']")).toBeVisible();
		await page.keyboard.press("Escape");

		await row_control(page, 0, ".ws-remove").click({ force: true });
		await expect(page.locator(".ws-row")).toHaveCount(2);

		await foot_button(page, "Save").click();
		// Gone from the app's arrangement, rather than shipped hidden.
		const rows = await saved_rows(page, APP_SAVE);
		expect(rows).toHaveLength(2);
		expect(rows.find((row) => row.link_to === "ToDo")).toBeUndefined();
	});

	test("refuses a section name another section already has, and says so under the label", async ({
		page,
	}) => {
		await add_through_panel(page, { kind: "Section", label: "Mine" });
		await page.locator(".ws-row").last().click();
		await page.locator(".ws-panel [data-fieldname='label'] input").fill("Records");

		await expect(page.locator(".ws-panel [data-fieldname='label']").first()).toContainText(
			"There is already a section called Records."
		);
		await expect(page.locator(".ws-row").last().locator(".sidebar-item-label")).not.toHaveText(
			"Records"
		);
	});

	test("closes quietly when the desk moves to another sidebar with nothing unsaved", async ({
		page,
	}) => {
		await expect(page.locator(".ws-row")).toHaveCount(3);
		await page.evaluate((module) => frappe.app.sidebar.select_shell(module), other_module);

		await expect(page.locator(".sidebar-editor")).toHaveCount(0);
		await expect(page.locator(".modal:visible")).toHaveCount(0);
		await expect(page.locator(".body-sidebar .sidebar-items")).toBeVisible();
	});

	test("asks before the desk moves to another sidebar with changes unsaved", async ({
		page,
	}) => {
		await row_control(page, 0, ".ws-remove").click({ force: true });
		await page.evaluate((module) => frappe.app.sidebar.select_shell(module), other_module);

		const prompt = page.locator(".modal:visible", { hasText: "Save your changes?" });
		await expect(prompt).toBeVisible();
		await prompt.getByRole("button", { name: "Discard" }).click();
		await expect(page.locator(".sidebar-editor")).toHaveCount(0);
		expect(await stubbed_calls(page)).not.toContain(SAVE);
	});
});

test.describe("Arrangement editor: an app's dock", () => {
	const READ = "frappe.desk.doctype.dock.dock.get_user_dock_layer";
	const BASE = "frappe.desk.doctype.dock.dock.get_app_dock_layer";
	const SAVE = "frappe.desk.doctype.dock.dock.save_user_dock";

	let modules;

	const bar_button = (page, label) =>
		page.locator(".ws-bar .ws-foot").getByRole("button", { name: label });
	const tiles = (page) => page.locator("#desk-dock .ws-tile");

	test.beforeEach(async ({ page, desk }) => {
		await open_desk(page, desk);
		await as_plain_user(page);

		// A dock entry names something the boot payload carries, so the app it arranges is built
		// from modules this site really has.
		modules = await page.evaluate(() => Object.keys(frappe.boot.module_sidebars).slice(0, 2));
		await stub_xcall(page, {
			[READ]: modules.map((name) => ({ link_type: "Sidebar", link_to: name, hidden: 0 })),
			[BASE]: [],
			[SAVE]: await page.evaluate(() => frappe.boot.dock),
		});
		await page.evaluate((modules) => {
			const app = {
				app_name: "frappe",
				app_title: "Frappe",
				dock: modules.map((name) => ({ link_type: "Sidebar", link_to: name })),
			};
			frappe.app.sidebar.get_sidebar_app = () => app;
			frappe.app.sidebar.dock_enabled = () => true;
			// The rail draws the site's resolved arrangement for the app, so it is this one too.
			delete frappe.boot.dock?.[app.app_name];
			frappe.app.sidebar.refresh_dock();
		}, modules);
	});

	async function open_dock_editor(page) {
		await page.evaluate(() => (window.__editor = new frappe.ui.DockManager()));
		await expect(tiles(page)).toHaveCount(modules.length);
	}

	test("edits the rail's own tiles, leaving the sidebar as it is", async ({ page }) => {
		await open_dock_editor(page);

		await expect(page.locator(".sidebar-editor")).toHaveCount(0);
		await expect(page.locator(".ws-bar .ws-bar-name")).toHaveText("Dock");
		await expect(page.locator(".ws-bar .ws-layer-phrase")).toHaveText("just for me");
	});

	test("holds a floating rail open without pinning it", async ({ page }) => {
		await page.evaluate(() => frappe.app.sidebar.dock.set_pinned(false));
		await open_dock_editor(page);

		await expect(page.locator("body")).toHaveClass(with_class("dock-open"));
		await expect(page.locator("body")).not.toHaveClass(with_class("dock-pinned"));
		// A click away from a floating rail would put it away; while it is edited it stays.
		await page.locator(".page-head, .layout-main").first().click({ force: true });
		await expect(page.locator("body")).toHaveClass(with_class("dock-open"));

		await bar_button(page, "Cancel").click();
		await expect(page.locator(".ws-bar")).toHaveCount(0);
		await expect(page.locator("body")).not.toHaveClass(with_class("dock-open"));
	});

	test("takes a tile off the rail from its panel, and saves it hidden", async ({ page }) => {
		await open_dock_editor(page);
		// A tile carries no control of its own; Remove sits beside its panel's close button.
		await expect(tiles(page).first().locator(".ws-remove")).toHaveCount(0);
		await tiles(page).first().click();
		await page
			.locator(".ws-panel .ws-panel-head")
			.getByRole("button", { name: "Remove" })
			.click();
		await expect(tiles(page)).toHaveCount(modules.length - 1);
		await expect(page.locator(".ws-panel")).toHaveCount(0);

		await bar_button(page, "Save").click();
		const rows = await saved_rows(page, SAVE);
		expect(rows.find((row) => row.link_to === modules[0]).hidden).toBe(1);
	});

	test("opens a tile's label and icon beside the rail, and saves what was changed", async ({
		page,
	}) => {
		await open_dock_editor(page);
		await tiles(page).first().click();
		await expect(page.locator(".ws-panel")).toBeVisible();

		// The panel passes changes on once it has settled.
		await page.waitForFunction(() => window.__editor.panel.ready);
		await page.evaluate(() => window.__editor.panel.field_group.set_value("title", "Renamed"));
		await expect(tiles(page).first()).toHaveAttribute("aria-label", "Renamed");

		await bar_button(page, "Save").click();
		const rows = await saved_rows(page, SAVE);
		expect(rows.find((row) => row.link_to === modules[0]).title).toBe("Renamed");
	});

	test("opens the editor when a tile is dragged, with the drop as its first change", async ({
		page,
	}) => {
		const items = page.locator("#desk-dock .dock-items .dock-item");
		await expect(items).toHaveCount(modules.length);
		await items.nth(1).dragTo(items.nth(0));

		await expect(tiles(page)).toHaveCount(modules.length);
		await expect(bar_button(page, "Save")).toBeEnabled();
		await bar_button(page, "Save").click();
		const rows = await saved_rows(page, SAVE);
		expect(rows.map((row) => row.link_to)).toEqual([modules[1], modules[0]]);
	});

	async function add_module_named(page, name) {
		await page.locator("#desk-dock .ws-add-row").click();
		await expect(page.locator(".ws-panel")).toBeVisible();
		await page.evaluate(
			(name) => window.__editor.panel.field_group.set_value("name", name),
			name
		);
		await page
			.locator(".ws-panel .ws-panel-foot")
			.getByRole("button", { name: "Add" })
			.click();
	}

	test("adds a module by name, created on Save before the layer that names it", async ({
		page,
	}) => {
		const ADD_MODULE = "frappe.desk.doctype.dock.dock.add_module";
		await stub_xcall(page, {
			[READ]: modules.map((name) => ({ link_type: "Sidebar", link_to: name, hidden: 0 })),
			[BASE]: [],
			[SAVE]: await page.evaluate(() => frappe.boot.dock),
			[ADD_MODULE]: await page.evaluate(() => ({
				workspace_pages: frappe.boot.workspaces,
				module_sidebars: {
					...frappe.boot.module_sidebars,
					"Field Trips": { name: "Field Trips", app: "frappe", header_icon: "folder" },
				},
				entity_module: frappe.boot.entity_module,
			})),
		});
		await page.evaluate(
			() => (frappe.model.can_create = (doctype) => doctype === "Module Def")
		);
		await open_dock_editor(page);

		await add_module_named(page, "Field Trips");
		await expect(tiles(page)).toHaveCount(modules.length + 1);
		// Nothing is created until Save, so Cancel would leave nothing behind.
		expect(await stubbed_calls(page)).not.toContain(ADD_MODULE);

		await bar_button(page, "Save").click();
		const rows = await saved_rows(page, SAVE);
		// A row a layer adds stores an icon of its own, so it takes the new module's.
		expect(rows.find((row) => row.link_to === "Field Trips")).toMatchObject({
			added: 1,
			icon: "folder",
			title: "Field Trips",
		});
		expect((await stubbed_calls(page)).filter((m) => m !== READ && m !== BASE)).toEqual([
			ADD_MODULE,
			SAVE,
		]);
		expect(await saved_args(page, ADD_MODULE)).toEqual({
			app: "frappe",
			module: "Field Trips",
		});
	});

	test("puts a tile taken off back when Add names it, rather than making another", async ({
		page,
	}) => {
		await page.evaluate(
			() => (frappe.model.can_create = (doctype) => doctype === "Module Def")
		);
		await open_dock_editor(page);
		await tiles(page).first().click();
		await page
			.locator(".ws-panel .ws-panel-head")
			.getByRole("button", { name: "Remove" })
			.click();
		await expect(tiles(page)).toHaveCount(modules.length - 1);

		await add_module_named(page, modules[0]);
		await expect(tiles(page)).toHaveCount(modules.length);
	});

	test("offers Add only to someone who may create a module", async ({ page }) => {
		await page.evaluate(() => (frappe.model.can_create = () => false));
		await open_dock_editor(page);
		await expect(page.locator("#desk-dock .ws-add-row")).toHaveCount(0);
	});

	test("stores no row for the app at all when Reset takes everything off", async ({ page }) => {
		await open_dock_editor(page);
		await page.locator(".ws-bar .ws-more").click();
		await page.locator('.es-menu [role="menuitem"]', { hasText: "Reset" }).first().click();
		await expect(tiles(page)).toHaveCount(0);

		await bar_button(page, "Save").click();
		// An empty dock is not stored as an empty dock: no row is stored for this app at all, so
		// the layer below shows through instead.
		expect(await saved_rows(page, SAVE)).toEqual([]);
	});
});
