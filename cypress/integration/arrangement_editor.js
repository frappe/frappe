// The editor every navigation surface is arranged in -- `frappe.ui.ArrangementEditor`, which the
// dock's manager and a module's sidebar editor are both built on.
//
// Most of it is driven through a test surface rather than through a real module, for the same
// reason `sidebar_resolution.js` drives the resolver directly: what a surface supplies is a
// handful of methods, so the machinery under test can be handed entries that are the same on
// every site and endpoints that answer without a round trip. Nothing about the editor itself is
// faked -- it is the real dialog, the real list, the real eye and the real save.
//
// Reordering by hand is not asserted here. A Sortable drag has to be synthesised from mouse
// events, and one that does not take leaves a test that passes for the wrong reason; what the
// drop *means* -- the preview following the arrangement, an entry joining the section it lands
// under -- is covered through the eye and through Add, which are the same code paths.
//
// The two surfaces then get tests of their own, using their real classes with their endpoints
// stubbed, for the things that are theirs alone: sections and membership on the sidebar, the
// app's own entries on the dock.

const ENTRIES = [
	{ key: "alpha", label: "Alpha" },
	{ key: "beta", label: "Beta" },
	{ key: "gamma", label: "Gamma" },
];

// Answer every endpoint from here, and keep what was asked so a test can assert on the save.
// Each test visits the desk again, so the stub never outlives the one that installed it.
function stub_xcall(win, handlers) {
	const calls = [];
	win.frappe.xcall = (method, args) => {
		calls.push({ method, args });
		const handler = handlers[method];
		return handler ? Promise.resolve().then(() => handler(args)) : Promise.resolve({});
	};
	win.__calls = calls;
	return calls;
}

// A surface with three entries and nothing else to it. `prepare` states the curation right rather
// than reading it off whoever is running the test, so the layer switch is testable both ways.
function open_editor(win, { hidden = [], can_curate = false } = {}) {
	const frappe = win.frappe;

	class TestSurface extends frappe.ui.ArrangementEditor {
		prepare() {
			this.can_curate_site = can_curate;
		}

		get layers() {
			return {
				user: { read: "read.user", save: "save.user", saved: () => "Saved" },
				site: { read: "read.site", save: "save.site", saved: () => "Saved for everyone" },
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
			return { items: this.arranged_rows((key, is_hidden) => ({ key, hidden: is_hidden })) };
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

	win.__editor = new TestSurface();
}

// The editor's own Save, addressed through the editor rather than through "whatever dialog is
// open". A dialog on its way out is the last visible modal for as long as its fade takes, and
// `get_open_dialog` hands back that one -- so a Save clicked after an Add lands on the Add
// button instead, and the arrangement is never sent.
function save_editor() {
	cy.window().then((win) => {
		cy.wrap(win.__editor.dialog.$wrapper).find(".btn-modal-primary").click();
	});
}

// Add a section through the dialog, and leave it closed behind.
//
// Choosing `Section` redraws the fields a link needs away, and a label typed into that redraw
// loses its first keystroke -- so the redraw is waited for and the field read back before it is
// sent. The dialog is then waited off the screen, so whatever is clicked next cannot be it.
function add_section(label) {
	cy.get_open_dialog().find(".ws-add").click();
	cy.fill_field("kind", "Section", "Select");
	cy.get_open_dialog().find('[data-fieldname="link_type"]').should("not.be.visible");
	cy.fill_field("label", label);
	cy.get_field("label").should("have.value", label);
	cy.get_open_dialog().find(".btn-modal-primary").click();
	cy.contains(".modal", "Add to the Sidebar").should("not.be.visible");
}

context("Arrangement editor", () => {
	before(() => {
		cy.login();
	});

	beforeEach(() => {
		cy.visit("/desk/todo");
		cy.desk_ready();
	});

	it("opens on one list holding everything, and a preview of what it leaves behind", () => {
		cy.window().then((win) => {
			stub_xcall(win, { "read.user": () => ENTRIES });
			open_editor(win);
		});

		cy.get(".ws-arrangement .ws-item").should("have.length", 3);
		cy.get(".ws-arrangement .ws-item-label").first().should("have.text", "Alpha");
		cy.get(".ws-preview .ws-preview-item").should("have.length", 3);
		cy.get(".ws-preview .ws-item-label").last().should("have.text", "Gamma");
	});

	it("keeps an entry the eye has off in the list, in its place, and out of the preview", () => {
		cy.window().then((win) => {
			stub_xcall(win, { "read.user": () => ENTRIES });
			open_editor(win, { hidden: ["beta"] });
		});

		// still on the list, and still second -- which is what makes it findable again
		cy.get(".ws-arrangement .ws-item").should("have.length", 3);
		cy.get(".ws-arrangement .ws-item").eq(1).should("have.class", "ws-item-hidden");
		cy.get(".ws-arrangement .ws-item")
			.eq(1)
			.find(".ws-item-label")
			.should("have.text", "Beta");

		cy.get(".ws-preview .ws-preview-item").should("have.length", 2);
		cy.get(".ws-preview").should("not.contain", "Beta");
	});

	it("takes an entry off with the eye and puts it back where it was", () => {
		cy.window().then((win) => {
			stub_xcall(win, { "read.user": () => ENTRIES });
			open_editor(win);
		});

		cy.get(".ws-arrangement .ws-item").eq(1).find(".ws-item-eye").click();
		cy.get(".ws-arrangement .ws-item").eq(1).should("have.class", "ws-item-hidden");
		cy.get(".ws-preview .ws-preview-item").should("have.length", 2);
		cy.get(".ws-preview").should("not.contain", "Beta");

		// ... and back on, into the place it never left
		cy.get(".ws-arrangement .ws-item").eq(1).find(".ws-item-eye").click();
		cy.get(".ws-arrangement .ws-item").eq(1).should("not.have.class", "ws-item-hidden");
		cy.get(".ws-preview .ws-item-label").eq(1).should("have.text", "Beta");
	});

	it("saves the whole arrangement, in order, the entries the eye has off included", () => {
		cy.window().then((win) => {
			stub_xcall(win, { "read.user": () => ENTRIES, "save.user": () => ({}) });
			open_editor(win);
		});

		cy.get(".ws-arrangement .ws-item").first().find(".ws-item-eye").click();
		save_editor();

		cy.window().then((win) => {
			const save = win.__calls.find((call) => call.method === "save.user");
			// an entry left out would keep whatever the layer below said about it, so every one
			// of them goes back, carrying its own flag
			expect(save.args.items).to.deep.equal([
				{ key: "alpha", hidden: 1 },
				{ key: "beta", hidden: 0 },
				{ key: "gamma", hidden: 0 },
			]);
		});
	});

	it("opens a curator on the site's layer, with the switch in the dialog's header", () => {
		cy.window().then((win) => {
			stub_xcall(win, { "read.user": () => ENTRIES, "read.site": () => ENTRIES });
			open_editor(win, { can_curate: true });
		});

		// arranging for everyone is what the right is for, so that is the layer it opens on
		cy.get_open_dialog().find(".modal-header .ws-layer-switch").should("have.value", "site");
		cy.get_open_dialog().find(".modal-header .ws-layer-switch").select("user");

		// the other layer is a different arrangement, so it is read rather than filtered
		cy.get(".ws-arrangement .ws-item").should("have.length", 3);
		cy.window().then((win) => {
			expect(win.__calls.map((call) => call.method)).to.deep.equal([
				"read.site",
				"read.user",
			]);
		});
	});

	it("gives somebody who may not curate for everyone their own layer and no switch", () => {
		cy.window().then((win) => {
			stub_xcall(win, { "read.user": () => ENTRIES });
			open_editor(win);
		});

		cy.get(".ws-arrangement .ws-item").should("have.length", 3);
		cy.get_open_dialog().find(".ws-layer-switch").should("not.exist");
		// their own is the only layer there is to open on, so it is the one that was read
		cy.window().then((win) => {
			expect(win.__calls.map((call) => call.method)).to.deep.equal(["read.user"]);
		});
	});

	it("says a read failed instead of sitting on Loading, and will not save what it never read", () => {
		cy.window().then((win) => {
			stub_xcall(win, {
				"read.user": () => Promise.reject(new Error("no arrangement for you")),
				"save.user": () => ({}),
			});
			open_editor(win);
		});

		cy.get_open_dialog().should("contain", "Could not load the arrangement.");
		save_editor();

		cy.window().then((win) => {
			expect(win.__calls.filter((call) => call.method === "save.user")).to.have.length(0);
		});
	});
});

context("Arrangement editor: a module's sidebar", () => {
	// What the read endpoint answers with: the layer as it arranges the sidebar, hidden entries
	// kept. A section and one member of it, so both halves of what a sidebar has and the dock
	// does not are on screen.
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

	before(() => {
		cy.login();
	});

	beforeEach(() => {
		cy.visit("/desk/todo");
		cy.desk_ready();
		cy.window().then((win) => {
			// Run as somebody without the shared curation right, so the editor opens on the one
			// layer these tests stub. Whether the account running them may curate for everyone is
			// a fact about the site, and which endpoint a save reaches should not turn on it --
			// the layer switch has its own test above.
			const has_role = win.frappe.user.has_role.bind(win.frappe.user);
			win.frappe.user.has_role = (role) =>
				role === "Workspace Manager" ? false : has_role(role);

			// The editor arranges the sidebar on screen, and `apply` redraws that sidebar from
			// the boot payload -- so it is pointed at a module the boot really carries.
			const module = Object.keys(win.frappe.boot.module_sidebars)[0];
			win.frappe.app.sidebar.current_module = module;

			stub_xcall(win, {
				[READ]: () => ITEMS.map((item) => ({ ...item })),
				[SAVE]: () => ({ module_sidebars: win.frappe.boot.module_sidebars }),
			});
			win.__editor = new win.frappe.ui.SidebarManager();
		});
	});

	it("says which entry is a section, and draws it as one in the preview", () => {
		cy.get(".ws-arrangement .ws-item").should("have.length", 3);
		cy.get(".ws-arrangement .ws-item")
			.eq(1)
			.find(".ws-item-chip")
			.should("have.text", "Section");

		// a header leads nowhere, so the preview draws it as a header rather than as a link
		cy.get(".ws-preview .ws-preview-section").should("have.text", "Records");
		cy.get(".ws-arrangement .ws-item").eq(2).should("have.class", "ws-item-child");
	});

	it("adds a section, and then puts what is added next into it", () => {
		add_section("Mine");

		// the section goes on the end...
		cy.get(".ws-arrangement .ws-item").should("have.length", 4);
		cy.get(".ws-arrangement .ws-item")
			.last()
			.find(".ws-item-chip")
			.should("have.text", "Section");

		// a URL rather than a document link: what is under test is where the entry lands, and a
		// Dynamic Link would drag a search box into a test that is not about one
		cy.get_open_dialog().find(".ws-add").click();
		cy.fill_field("link_type", "URL", "Select");
		// same redraw, the other way round: the URL field is what arrives, and it is typed into
		// once it has
		cy.get_open_dialog().find('[data-fieldname="url"]').should("be.visible");
		cy.fill_field("url", "https://example.com");
		// The label is set rather than typed. A field group refreshes its dependencies 100ms
		// after any field changes (`FieldGroup.make`), and that redraw rewrites every input from
		// the model -- so the URL's own commit lands in the middle of the next field being typed
		// and takes what was typed before it with it, which is how "Elsewhere" arrives as
		// "lsewhere". What is under test here is where the entry lands, not the Data control.
		cy.window().then((win) => win.cur_dialog.set_value("label", "Elsewhere"));
		cy.get_field("label").should("have.value", "Elsewhere");
		cy.get_open_dialog().find(".btn-modal-primary").click();

		// ... and the entry added after it lands under it, which is what puts it in it
		cy.get(".ws-arrangement .ws-item").should("have.length", 5);
		cy.get(".ws-arrangement .ws-item").last().should("have.class", "ws-item-child");
		cy.get(".ws-preview .ws-preview-item").last().should("have.class", "ws-item-child");
	});

	it("removes an entry this layer added rather than hiding it", () => {
		add_section("Mine");

		// nothing below holds it, so there is no hiding it -- it carries a cross, not an eye
		cy.get(".ws-arrangement .ws-item").last().find(".ws-item-eye").should("not.exist");
		cy.get(".ws-arrangement .ws-item").last().find(".ws-item-remove").click();
		cy.get(".ws-arrangement .ws-item").should("have.length", 3);
	});

	it("sends an added section without a key, for the server to name", () => {
		add_section("Mine");

		cy.get(".ws-arrangement .ws-item").should("have.length", 4);
		save_editor();

		cy.window().then((win) => {
			const rows = JSON.parse(win.__calls.find((call) => call.method === SAVE).args.items);
			const added = rows.find((row) => row.added);

			expect(added.type).to.equal("Section Break");
			expect(added.label).to.equal("Mine");
			// a row that leads nowhere is named by a hash of its type and its label, and the
			// server is what works that out
			expect(added.key).to.equal(null);
		});
	});
});

context("Arrangement editor: an app's dock", () => {
	const READ = "frappe.desk.doctype.dock.dock.get_user_dock_layer";
	const BASE = "frappe.desk.doctype.dock.dock.get_app_dock_layer";
	const SAVE = "frappe.desk.doctype.dock.dock.save_user_dock";

	before(() => {
		cy.login();
	});

	beforeEach(() => {
		cy.visit("/desk/todo");
		cy.desk_ready();
		cy.window().then((win) => {
			// Run as somebody without the shared curation right, so the editor opens on the one
			// layer these tests stub. Whether the account running them may curate for everyone is
			// a fact about the site, and which endpoint a save reaches should not turn on it --
			// the layer switch has its own test above.
			const has_role = win.frappe.user.has_role.bind(win.frappe.user);
			win.frappe.user.has_role = (role) =>
				role === "Workspace Manager" ? false : has_role(role);

			// A dock entry names something the boot payload carries -- an entry it does not is
			// one this user may see nothing in, and is not offerable. So the app it arranges is
			// built out of modules this site really has.
			const modules = Object.keys(win.frappe.boot.module_sidebars).slice(0, 2);
			win.__modules = modules;
			win.__app = {
				app_name: "frappe",
				app_title: "Frappe",
				dock: modules.map((name) => ({ type: "Sidebar", name })),
			};
			win.frappe.app.sidebar.get_sidebar_app = () => win.__app;

			stub_xcall(win, {
				[READ]: () => modules.map((name) => ({ type: "Sidebar", name, hidden: 0 })),
				[BASE]: () => [],
				[SAVE]: () => win.frappe.boot.dock,
			});
			win.__editor = new win.frappe.ui.DockManager();
		});
	});

	it("arranges the app's entries in the same list and preview the sidebar uses", () => {
		cy.window().then((win) => {
			cy.get(".ws-arrangement .ws-item").should("have.length", win.__modules.length);
			cy.get(".ws-preview .ws-preview-item").should("have.length", win.__modules.length);
		});
		cy.get_open_dialog().should("contain", "The dock as this arrangement leaves it.");
	});

	it("takes an entry off the dock with the same eye", () => {
		cy.get(".ws-arrangement .ws-item").first().find(".ws-item-eye").click();

		cy.window().then((win) => {
			cy.get(".ws-arrangement .ws-item").should("have.length", win.__modules.length);
			cy.get(".ws-preview .ws-preview-item").should("have.length", win.__modules.length - 1);
		});
	});

	it("stores no row for the app at all when Reset takes everything off", () => {
		cy.get_open_dialog().find(".ws-reset").click();
		cy.get(".ws-preview").should("contain", "Nothing on the dock");

		save_editor();
		cy.window().then((win) => {
			const save = win.__calls.find((call) => call.method === SAVE);
			// an empty dock is not stored as "an empty dock": no row is stored for this app at
			// all, so the layer below shows through instead
			expect(JSON.parse(save.args.items)).to.deep.equal([]);
		});
	});
});

context("Arrangement editor: making a module from the dock", () => {
	const SITE_READ = "frappe.desk.doctype.dock.dock.get_site_dock_layer";
	const BASE = "frappe.desk.doctype.dock.dock.get_app_dock_layer";
	const CREATE = "frappe.desk.doctype.dock.dock.create_module";
	const MADE = "Test Dock Made Module";

	before(() => {
		cy.login();
	});

	beforeEach(() => {
		cy.visit("/desk/todo");
		cy.desk_ready();
		cy.window().then((win) => {
			// Making a module is site content everybody boots, so it is behind the same right the
			// site layer is -- which is also the layer a curator opens on.
			const has_role = win.frappe.user.has_role.bind(win.frappe.user);
			win.frappe.user.has_role = (role) =>
				role === "Workspace Manager" ? true : has_role(role);

			const module = Object.keys(win.frappe.boot.module_sidebars)[0];
			// one object, handed back every time it is asked, the way the boot payload's own is
			// -- `place` pushes the new module onto its entry set
			win.__app = {
				app_name: "frappe",
				app_title: "Frappe",
				dock: [{ type: "Sidebar", name: module }],
			};
			win.frappe.app.sidebar.get_sidebar_app = () => win.__app;

			stub_xcall(win, {
				[SITE_READ]: () => [{ type: "Sidebar", name: module, hidden: 0 }],
				[BASE]: () => [],
				// What the endpoint answers with: the entry the dock now offers, plus everything
				// a workspace write invalidates -- the workspace list included, since a page the
				// boot has never heard of is one the desk cannot place.
				[CREATE]: () => ({
					entry: { type: "Sidebar", name: MADE },
					workspace_pages: {
						...win.frappe.boot.workspaces,
						pages: [
							...win.frappe.boot.workspaces.pages,
							{ name: MADE, title: MADE, module: MADE, public: 1 },
						],
					},
					app_data: win.frappe.boot.app_data,
					entity_module: win.frappe.boot.entity_module,
					module_sidebars: {
						...win.frappe.boot.module_sidebars,
						[MADE]: { module: MADE, label: MADE, header_icon: "box", items: [] },
					},
				}),
			});
			win.__editor = new win.frappe.ui.DockManager();
		});
	});

	it("puts a module it has just made straight onto the arrangement", () => {
		cy.get(".ws-arrangement .ws-item").should("have.length", 1);

		cy.get_open_dialog().find(".ws-add").click();
		cy.fill_field("module", MADE);
		cy.get_open_dialog().find(".btn-modal-primary").click();

		// it is on the dock the moment it exists; saving this arrangement is what says where
		cy.get(".ws-arrangement .ws-item").should("have.length", 2);
		cy.get(".ws-arrangement .ws-item-label").last().should("have.text", MADE);
		cy.get(".ws-preview .ws-item-label").last().should("have.text", MADE);

		cy.window().then((win) => {
			const call = win.__calls.find((one) => one.method === CREATE);
			expect(call.args.module).to.equal(MADE);
			expect(call.args.app).to.equal("frappe");
			// and the desk knows the page now, rather than meeting one its boot never heard of
			expect(win.frappe.boot.workspaces.pages.map((page) => page.name)).to.include(MADE);
		});
	});
});
