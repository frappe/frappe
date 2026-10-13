import { test, expect } from "../support";

const ENTRIES = [
	{ key: "alpha", label: "Alpha" },
	{ key: "beta", label: "Beta" },
	{ key: "gamma", label: "Gamma" },
];

const with_class = (name) => new RegExp(`(^|\\s)${name}(\\s|$)`);

async function open_desk(page, desk) {
	await page.goto("/desk/todo");
	await desk.ready();
	await page.evaluate(async () => {
		await frappe.require("arrangement_editor.bundle.js");
	});
}

// The desk behind the dialog keeps calling the server, and those calls land on the stub too, so
// the endpoints a test answers are recorded by name and told apart from the rest.
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

async function open_editor(page, { hidden = [], can_curate = false } = {}) {
	await page.evaluate(
		([hidden, can_curate]) => {
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
							saved: () => "Saved",
						},
						site: {
							read: "read.site",
							save: "save.site",
							label: () => "For everyone",
							condition: () => this.can_curate_site,
							saved: () => "Saved for everyone",
						},
					};
				}

				title() {
					return "Arrange the test surface";
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
					this.render_panes();
				}

				copy() {
					return {
						list_head: "Entries",
						list_sub: "Drag to reorder.",
						reset_title: "Take everything off",
						list_empty: "Nothing to arrange",
						preview_head: "Preview",
						preview_sub: "As it will look.",
						preview_empty: "Nothing on the surface",
						load_error: "Could not load the arrangement.",
					};
				}
			}

			window.__editor = new TestSurface();
		},
		[hidden, can_curate]
	);
}

// The editor's own Save is reached through the editor: a dialog on its way out is still the last
// visible modal while it fades, so a Save looked up on the open dialog right after an Add would
// land on the Add button.
async function save_editor(page) {
	const save = await page.waitForFunction(
		() => window.__editor.dialog?.$wrapper.find(".btn-modal-primary")[0]
	);
	await save.asElement().click();
}

// A dialog takes focus once it has finished opening, which would take whatever is being typed
// away from its field.
async function open_add_dialog(page, desk) {
	await desk.get_open_dialog().locator(".ws-add").click();
	await page.waitForFunction(() => cur_dialog?.display && cur_dialog.fields_dict.kind);
}

// Choosing `Section` redraws the dialog, and a label typed into that redraw loses its first
// keystroke, so the redraw is waited for and the field read back before it is sent.
async function add_section(page, desk, label) {
	await open_add_dialog(page, desk);
	await desk.fill_field("kind", "Section", "Select");
	await expect(
		desk.get_open_dialog().locator('[data-fieldname="link_type"]').first()
	).toBeHidden();
	await desk.fill_field("label", label);
	await expect(desk.get_field("label")).toHaveValue(label);
	await desk.get_open_dialog().locator(".btn-modal-primary").click();
	await expect(page.locator(".modal", { hasText: /Add to the Sidebar/ }).first()).toBeHidden();
}

// The editor then opens on the user's own layer, whatever the account running the test may
// curate for everyone.
async function drop_curation_right(page) {
	await page.evaluate(() => {
		const has_role = frappe.user.has_role.bind(frappe.user);
		frappe.user.has_role = (role) => (role === "Workspace Manager" ? false : has_role(role));
	});
}

test.describe("Arrangement editor", () => {
	test.beforeEach(async ({ page, desk }) => {
		await open_desk(page, desk);
	});

	test("opens on one list holding everything, and a preview of what it leaves behind", async ({
		page,
	}) => {
		await stub_xcall(page, { "read.user": ENTRIES });
		await open_editor(page);

		await expect(page.locator(".ws-arrangement .ws-item")).toHaveCount(3);
		await expect(page.locator(".ws-arrangement .ws-item-label").first()).toHaveText("Alpha");
		await expect(page.locator(".ws-preview .ws-preview-item")).toHaveCount(3);
		await expect(page.locator(".ws-preview .ws-item-label").last()).toHaveText("Gamma");
	});

	test("keeps an entry the eye has off in the list, in its place, and out of the preview", async ({
		page,
	}) => {
		await stub_xcall(page, { "read.user": ENTRIES });
		await open_editor(page, { hidden: ["beta"] });

		const items = page.locator(".ws-arrangement .ws-item");
		await expect(items).toHaveCount(3);
		await expect(items.nth(1)).toHaveClass(with_class("ws-item-hidden"));
		await expect(items.nth(1).locator(".ws-item-label")).toHaveText("Beta");

		await expect(page.locator(".ws-preview .ws-preview-item")).toHaveCount(2);
		await expect(page.locator(".ws-preview")).not.toContainText("Beta");
	});

	test("takes an entry off with the eye and puts it back where it was", async ({ page }) => {
		await stub_xcall(page, { "read.user": ENTRIES });
		await open_editor(page);

		const second = page.locator(".ws-arrangement .ws-item").nth(1);
		await second.locator(".ws-item-eye").click();
		await expect(second).toHaveClass(with_class("ws-item-hidden"));
		await expect(page.locator(".ws-preview .ws-preview-item")).toHaveCount(2);
		await expect(page.locator(".ws-preview")).not.toContainText("Beta");

		await second.locator(".ws-item-eye").click();
		await expect(second).not.toHaveClass(with_class("ws-item-hidden"));
		await expect(page.locator(".ws-preview .ws-item-label").nth(1)).toHaveText("Beta");
	});

	test("saves the whole arrangement, in order, the entries the eye has off included", async ({
		page,
	}) => {
		await stub_xcall(page, { "read.user": ENTRIES, "save.user": {} });
		await open_editor(page);

		await page.locator(".ws-arrangement .ws-item").first().locator(".ws-item-eye").click();
		await save_editor(page);

		await expect
			.poll(async () => (await saved_args(page, "save.user"))?.items)
			.toEqual([
				{ key: "alpha", hidden: 1 },
				{ key: "beta", hidden: 0 },
				{ key: "gamma", hidden: 0 },
			]);
	});

	test("opens a curator on the site's layer, with the switch in the dialog's header", async ({
		page,
		desk,
	}) => {
		await stub_xcall(page, { "read.user": ENTRIES, "read.site": ENTRIES });
		await open_editor(page, { can_curate: true });

		const layer_switch = desk.get_open_dialog().locator(".modal-header .ws-layer-switch");
		await expect(layer_switch).toHaveValue("site");
		await layer_switch.selectOption("user");

		await expect(page.locator(".ws-arrangement .ws-item")).toHaveCount(3);
		await expect.poll(() => stubbed_calls(page)).toEqual(["read.site", "read.user"]);
	});

	test("gives somebody who may not curate for everyone their own layer and no switch", async ({
		page,
		desk,
	}) => {
		await stub_xcall(page, { "read.user": ENTRIES });
		await open_editor(page);

		await expect(page.locator(".ws-arrangement .ws-item")).toHaveCount(3);
		await expect(desk.get_open_dialog().locator(".ws-layer-switch")).toHaveCount(0);
		expect(await stubbed_calls(page)).toEqual(["read.user"]);
	});

	test("says a read failed instead of sitting on Loading, and will not save what it never read", async ({
		page,
		desk,
	}) => {
		await stub_xcall(page, { "save.user": {} }, { "read.user": "no arrangement for you" });
		await open_editor(page);

		await expect(desk.get_open_dialog()).toContainText("Could not load the arrangement.");
		await save_editor(page);

		expect(await saved_args(page, "save.user")).toBeNull();
	});
});

test.describe("Arrangement editor: a module's sidebar", () => {
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

	test.beforeEach(async ({ page, desk }) => {
		await open_desk(page, desk);
		await drop_curation_right(page);

		const module_sidebars = await page.evaluate(() => frappe.boot.module_sidebars);
		await stub_xcall(page, { [READ]: ITEMS, [SAVE]: { module_sidebars } });
		await page.evaluate(() => {
			// `apply` redraws the sidebar on screen from the boot payload, so the editor is
			// pointed at a module the boot really carries.
			frappe.app.sidebar.current_module = Object.keys(frappe.boot.module_sidebars)[0];
			window.__editor = new frappe.ui.SidebarManager();
		});
	});

	test("says which entry is a section, and draws it as one in the preview", async ({ page }) => {
		const items = page.locator(".ws-arrangement .ws-item");
		await expect(items).toHaveCount(3);
		await expect(items.nth(1).locator(".ws-item-chip")).toHaveText("Section");

		await expect(page.locator(".ws-preview .ws-preview-section")).toHaveText("Records");
		await expect(items.nth(2)).toHaveClass(with_class("ws-item-child"));
	});

	test("adds a section, and then puts what is added next into it", async ({ page, desk }) => {
		await add_section(page, desk, "Mine");

		const items = page.locator(".ws-arrangement .ws-item");
		await expect(items).toHaveCount(4);
		await expect(items.last().locator(".ws-item-chip")).toHaveText("Section");

		await open_add_dialog(page, desk);
		await desk.fill_field("link_type", "URL", "Select");
		await expect(
			desk.get_open_dialog().locator('[data-fieldname="url"]').first()
		).toBeVisible();
		// A field's value reaches the model on blur, and every redraw of the dialog rewrites the
		// inputs from the model, so the URL is committed before anything else is touched.
		const url = await desk.fill_field("url", "https://example.com");
		await url.blur();
		// The label is set rather than typed: the field group refreshes its dependencies 100ms
		// after any field changes, and that redraw takes the first keystroke of the next field.
		await page.evaluate(async () => {
			await cur_dialog.set_value("label", "Elsewhere");
		});
		await expect(desk.get_field("label")).toHaveValue("Elsewhere");
		await expect(desk.get_field("url")).toHaveValue("https://example.com");
		await desk.get_open_dialog().locator(".btn-modal-primary").click();

		await expect(items).toHaveCount(5);
		await expect(items.last()).toHaveClass(with_class("ws-item-child"));
		await expect(page.locator(".ws-preview .ws-preview-item").last()).toHaveClass(
			with_class("ws-item-child")
		);
	});

	test("removes an entry this layer added rather than hiding it", async ({ page, desk }) => {
		await add_section(page, desk, "Mine");

		const items = page.locator(".ws-arrangement .ws-item");
		await expect(items.last().locator(".ws-item-eye")).toHaveCount(0);
		await items.last().locator(".ws-item-remove").click();
		await expect(items).toHaveCount(3);
	});

	test("sends an added section without a key, for the server to name", async ({
		page,
		desk,
	}) => {
		await add_section(page, desk, "Mine");

		await expect(page.locator(".ws-arrangement .ws-item")).toHaveCount(4);
		await save_editor(page);

		await expect.poll(() => saved_args(page, SAVE)).not.toBeNull();
		const rows = JSON.parse((await saved_args(page, SAVE)).items);
		const added = rows.find((row) => row.added);

		expect(added.type).toBe("Section Break");
		expect(added.label).toBe("Mine");
		expect(added.key).toBeNull();
	});
});

test.describe("Arrangement editor: an app's dock", () => {
	const READ = "frappe.desk.doctype.dock.dock.get_user_dock_layer";
	const BASE = "frappe.desk.doctype.dock.dock.get_app_dock_layer";
	const SAVE = "frappe.desk.doctype.dock.dock.save_user_dock";

	let modules;

	test.beforeEach(async ({ page, desk }) => {
		await open_desk(page, desk);
		await drop_curation_right(page);

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
			window.__editor = new frappe.ui.DockManager();
		}, modules);
	});

	test("arranges the app's entries in the same list and preview the sidebar uses", async ({
		page,
		desk,
	}) => {
		await expect(page.locator(".ws-arrangement .ws-item")).toHaveCount(modules.length);
		await expect(page.locator(".ws-preview .ws-preview-item")).toHaveCount(modules.length);
		await expect(desk.get_open_dialog()).toContainText(
			"The dock as this arrangement leaves it."
		);
	});

	test("takes an entry off the dock with the same eye", async ({ page }) => {
		await page.locator(".ws-arrangement .ws-item").first().locator(".ws-item-eye").click();

		await expect(page.locator(".ws-arrangement .ws-item")).toHaveCount(modules.length);
		await expect(page.locator(".ws-preview .ws-preview-item")).toHaveCount(modules.length - 1);
	});

	test("stores no row for the app at all when Reset takes everything off", async ({
		page,
		desk,
	}) => {
		await desk.get_open_dialog().locator(".ws-reset").click();
		await expect(page.locator(".ws-preview")).toContainText("Nothing on the dock");

		await save_editor(page);
		await expect.poll(() => saved_args(page, SAVE)).not.toBeNull();
		expect(JSON.parse((await saved_args(page, SAVE)).items)).toEqual([]);
	});
});
