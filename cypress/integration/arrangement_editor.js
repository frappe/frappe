// The editor every navigation surface is arranged in: `frappe.ui.ArrangementEditor`, which the
// dock's manager and a module's sidebar editor are both built on.
//
// Most of it is driven through a test surface rather than a real module, for the same reason
// `sidebar_resolution.js` drives the resolver directly: what a surface supplies is a handful of
// methods, so the machinery under test can be given entries that are the same on every site and
// endpoints that answer without a round trip. Nothing about the editor itself is faked; it is the
// real dialog, list, eye and save.
//
// Reordering by hand is not asserted here. A Sortable drag has to be synthesised from mouse
// events, and one that does not take leaves a test that passes for the wrong reason. What the drop
// means, such as the preview following the arrangement and an entry joining the section it lands
// under, is covered through the eye and through Add, which are the same code paths.
//
// The two surfaces then get tests of their own, using their real classes with their endpoints
// stubbed, for what is specific to each: sections and membership on the sidebar, and the app's own
// entries on the dock.

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
	// The desk behind the dialog keeps talking to the server, such as a list view counting its
	// rows, and those calls land here too. A test about what the editor asked for means the
	// endpoints it was given, so they are named rather than inferred from whatever was recorded.
	win.__stubbed = new Set(Object.keys(handlers));
	return calls;
}

// The stubbed endpoints the editor reached, in order.
function stubbed_calls(win) {
	return win.__calls.map((call) => call.method).filter((method) => win.__stubbed.has(method));
}

// The editor is not in the desk bundle; it arrives when a menu item asks for it. These tests build
// their editors by hand instead of going through a menu, so each pulls the bundle in for itself,
// the same way those menu items do.
function load_editor_bundle() {
	cy.window().then((win) => win.frappe.require("arrangement_editor.bundle.js"));
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

// The editor's own Save, addressed through the editor rather than through whatever dialog is
// open. A dialog on its way out is the last visible modal for as long as its fade takes, and
// `get_open_dialog` returns that one, so a Save clicked after an Add would land on the Add button
// and the arrangement would never be sent.
function save_editor() {
	cy.window().then((win) => {
		cy.wrap(win.__editor.dialog.$wrapper).find(".btn-modal-primary").click();
	});
}

// Add a section through the dialog, and leave it closed afterwards.
//
// Choosing `Section` redraws the dialog, removing the fields a link needs, and a label typed into
// that redraw loses its first keystroke, so the redraw is waited for and the field read back
// before it is sent. The dialog is then waited off the screen, so whatever is clicked next cannot
// be it.
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
		load_editor_bundle();
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

		// Still on the list, and still second, which is what makes it findable again.
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

		// And back on, into the place it never left.
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
			// An entry left out would keep whatever the layer below said about it, so every entry
			// goes back, carrying its own flag.
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

		// Arranging for everyone is what the permission is for, so that is the layer it opens on.
		cy.get_open_dialog().find(".modal-header .ws-layer-switch").should("have.value", "site");
		cy.get_open_dialog().find(".modal-header .ws-layer-switch").select("user");

		// The other layer is a different arrangement, so it is read rather than filtered.
		cy.get(".ws-arrangement .ws-item").should("have.length", 3);
		cy.window().then((win) => {
			expect(stubbed_calls(win)).to.deep.equal(["read.site", "read.user"]);
		});
	});

	it("gives somebody who may not curate for everyone their own layer and no switch", () => {
		cy.window().then((win) => {
			stub_xcall(win, { "read.user": () => ENTRIES });
			open_editor(win);
		});

		cy.get(".ws-arrangement .ws-item").should("have.length", 3);
		cy.get_open_dialog().find(".ws-layer-switch").should("not.exist");
		// Their own is the only layer to open on, so it is the one that was read.
		cy.window().then((win) => {
			expect(stubbed_calls(win)).to.deep.equal(["read.user"]);
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

	before(() => {
		cy.login();
	});

	beforeEach(() => {
		cy.visit("/desk/todo");
		cy.desk_ready();
		load_editor_bundle();
		cy.window().then((win) => {
			// Run as a user without the shared curation right, so the editor opens on the one
			// layer these tests stub. Whether the account running them may curate for everyone is
			// a fact about the site, and which endpoint a save reaches should not depend on it.
			// The layer switch has its own test above.
			const has_role = win.frappe.user.has_role.bind(win.frappe.user);
			win.frappe.user.has_role = (role) =>
				role === "Workspace Manager" ? false : has_role(role);

			// Run as a user without the shared curation right, so the editor opens on the one
			// The editor arranges the sidebar on screen, and `apply` redraws that sidebar from
			// the boot payload, so it is pointed at a module the boot really carries.
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

		// A header leads nowhere, so the preview draws it as a header rather than as a link.
		cy.get(".ws-preview .ws-preview-section").should("have.text", "Records");
		cy.get(".ws-arrangement .ws-item").eq(2).should("have.class", "ws-item-child");
	});

	it("adds a section, and then puts what is added next into it", () => {
		add_section("Mine");

		// The section goes on the end.
		cy.get(".ws-arrangement .ws-item").should("have.length", 4);
		cy.get(".ws-arrangement .ws-item")
			.last()
			.find(".ws-item-chip")
			.should("have.text", "Section");

		// A URL rather than a document link: what is under test is where the entry lands, and a
		// Dynamic Link would bring a search box into a test that is not about one.
		cy.get_open_dialog().find(".ws-add").click();
		cy.fill_field("link_type", "URL", "Select");
		// The same redraw, the other way round: the URL field is what arrives, and it is typed
		// into once it has.
		cy.get_open_dialog().find('[data-fieldname="url"]').should("be.visible");
		// The URL is committed before anything else is touched. A field's value reaches the model
		// on blur, and every redraw of the dialog rewrites the inputs from the model, so a URL
		// still sitting in its input is wiped by the next redraw and Add is refused for a missing
		// URL.
		cy.fill_field("url", "https://example.com").blur();
		// The label is then set rather than typed. A field group refreshes its dependencies 100ms
		// after any field changes (`FieldGroup.make`), and that redraw lands between the first
		// keystroke of the next field and its second, taking the first with it, which is how
		// "Elsewhere" arrives as "lsewhere". What is under test here is where the entry lands, not
		// the Data control.
		cy.window().then((win) => win.cur_dialog.set_value("label", "Elsewhere"));
		cy.get_field("label").should("have.value", "Elsewhere");
		// Both halves of the entry are on the dialog, so Add cannot be refused for a value the
		// redraw removed.
		cy.get_field("url").should("have.value", "https://example.com");
		cy.get_open_dialog().find(".btn-modal-primary").click();

		// The entry added after it lands under it, which is what puts it in the section.
		cy.get(".ws-arrangement .ws-item").should("have.length", 5);
		cy.get(".ws-arrangement .ws-item").last().should("have.class", "ws-item-child");
		cy.get(".ws-preview .ws-preview-item").last().should("have.class", "ws-item-child");
	});

	it("removes an entry this layer added rather than hiding it", () => {
		add_section("Mine");

		// Nothing below holds it, so there is no hiding it: it carries a cross, not an eye.
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
			// A row that leads nowhere is named by a hash of its type and label, and the server
			// computes that.
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
		load_editor_bundle();
		cy.window().then((win) => {
			// Run as a user without the shared curation right, so the editor opens on the one
			// layer these tests stub. Whether the account running them may curate for everyone is
			// a fact about the site, and which endpoint a save reaches should not depend on it.
			// The layer switch has its own test above.
			const has_role = win.frappe.user.has_role.bind(win.frappe.user);
			win.frappe.user.has_role = (role) =>
				role === "Workspace Manager" ? false : has_role(role);

			// A dock entry names something the boot payload carries. An entry it does not carry
			// is one this user can see nothing in, and is not offered. So the app it arranges
			// is built from modules this site really has.
			const modules = Object.keys(win.frappe.boot.module_sidebars).slice(0, 2);
			win.__modules = modules;
			win.__app = {
				app_name: "frappe",
				app_title: "Frappe",
				dock: modules.map((name) => ({ link_type: "Sidebar", link_to: name })),
			};
			win.frappe.app.sidebar.get_sidebar_app = () => win.__app;

			stub_xcall(win, {
				[READ]: () =>
					modules.map((name) => ({ link_type: "Sidebar", link_to: name, hidden: 0 })),
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
