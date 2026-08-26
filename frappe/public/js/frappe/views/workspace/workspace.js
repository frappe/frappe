import EditorJS from "@editorjs/editorjs";
import Undo from "editorjs-undo";

// sentinel class on the injected "this workspace is hidden" notice block, so it can be
// rendered for Workspace Managers but stripped before the content is saved.
const HIDDEN_NOTICE_MARKER = "workspace-hidden-notice";

// Rail id for the Manage Workspaces group holding workspaces with no module at all. Every tab
// there is identified by its module name, and "" is not usable as one: `SettingsDialog` keys its
// items by id and treats a falsy one as "no tab".
const NO_MODULE_TAB = "__no_module__";

// "Access" options in the New Workspace dialog -- a virtual field that maps to the
// underlying `public` / `for_user` / `roles` fields:
//   private -> personal (public=0, for_user=current user)
//   group   -> public but role-gated (public=1, roles=[...])
//   public  -> visible to everyone (public=1, no roles)
const ACCESS_PRIVATE = __("Only to you");
const ACCESS_GROUP = __("To a group of users");
const ACCESS_PUBLIC = __("To everyone");

// `content` arrives as a JSON string on the boot payload. Parse it defensively: a single row
// whose content was mangled (see the seeding comment in `initialize_new_page`) would otherwise
// throw out of the constructor and take the whole desk down with it, leaving no way in to fix it.
function parse_content(workspace) {
	if (typeof workspace.content != "string") return;
	try {
		workspace.content = JSON.parse(workspace.content);
	} catch (e) {
		console.error(`Workspace "${workspace.name}" has unreadable content`, e);
		workspace.content = [];
	}
}

frappe.standard_pages["Workspaces"] = function () {
	var wrapper = frappe.container.add_page("Workspaces");

	frappe.ui.make_app_page({
		parent: wrapper,
		name: "Workspaces",
		title: __("Workspace"),
		single_column: true,
		hide_sidebar: false,
	});

	frappe.workspace = new frappe.views.Workspace(wrapper);
	$(wrapper).bind("show", function () {
		frappe.workspace.show();
	});
};

frappe.views.Workspace = class Workspace {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = wrapper.page;
		this.workspaces = frappe.boot.workspaces.pages;

		this.blocks = frappe.workspace_block.blocks;
		this.is_read_only = true;
		this.pages = {};
		this.current_page = {};
		this.sidebar_items = {
			public: {},
			private: {},
		};
		this.prepare_container();
		this.sidebar = frappe.app.sidebar;
		this.cached_pages = $.extend(true, {}, frappe.boot.workspaces);
		this.has_access = frappe.boot.workspaces.has_access;
		this.has_create_access = frappe.boot.workspaces.has_create_access;
		this.setup();
		this.show();
		this.register_awesomebar_shortcut();
	}
	setup() {
		const me = this;
		this.workspaces.map((workspace) => {
			workspace.is_editable = !workspace.public || me.has_access;
			parse_content(workspace);
		});
	}

	setup_sidebar() {
		if (this._page) {
			this.sidebar.setup(this._page.name);
		}
	}

	// The modules a workspace can be assigned to, memoised for the life of the view -- the New
	// Workspace dialog, the Manage Workspaces panel and the "not on any dock" prompt all need
	// the same list, and the installed modules don't change under us.
	get_assignable_modules() {
		if (!this._assignable_modules) {
			this._assignable_modules = frappe
				.xcall("frappe.desk.doctype.workspace.workspace.get_assignable_modules")
				.then((modules) => modules || [])
				// Drop the memo on failure. A cached rejected promise would hand the same error
				// to every later caller, so one dropped request would leave the New Workspace
				// dialog and the Manage panel broken for the rest of the session.
				.catch((e) => {
					this._assignable_modules = null;
					throw e;
				});
		}
		return this._assignable_modules;
	}

	// Modules are grouped by app in the label, since two apps can ship similarly named modules.
	// A module the site owns is placed into no app's dock and has no app to name, so it reads as
	// itself rather than claiming one.
	module_select_options(modules) {
		return modules.map((m) => ({
			value: m.module,
			label: m.app_title ? `${__(m.label)} (${__(m.app_title)})` : __(m.label),
		}));
	}

	prepare_container() {
		this.body = this.wrapper.find(".layout-main-section");
		this.$page = $(`<div class="editor-js-container"></div>`).appendTo(this.body);
	}

	show() {
		if (!this.workspaces) {
			// pages not yet loaded, call again after a bit
			setTimeout(() => this.show(), 100);
			return;
		}

		let page = this.get_page_to_show();
		if (this._page?.name === page.name) return; // already shown

		if (!frappe.router.current_route[0]) {
			frappe.route_flags.replace_route = true;
			frappe.set_route(frappe.router.slug(page.public ? page.name : "private/" + page.name));
			return;
		}

		this.page.set_title(__(page.name));
		this.show_page(page);
	}

	get_data(page) {
		return frappe
			.call({
				method: "frappe.desk.desktop.get_desktop_page",
				args: {
					// send sorted min requirements to increase chance of cache hit
					page: { name: page.name, title: page.title, public: page.public },
				},
				type: "GET",
			})
			.then((data) => {
				this.page_data = data.message;

				// caching page data
				this.pages[page.name] && delete this.pages[page.name];
				this.pages[page.name] = data.message;

				if (!this.page_data || Object.keys(this.page_data).length === 0) return;
				if (this.page_data.charts && this.page_data.charts.items.length === 0) return;

				return frappe.dashboard_utils.get_dashboard_settings().then((settings) => {
					if (settings) {
						let chart_config = settings.chart_config
							? JSON.parse(settings.chart_config)
							: {};
						this.page_data.charts.items.map((chart) => {
							chart.chart_settings = chart_config[chart.chart_name] || {};
						});
						this.pages[page.name] = this.page_data;
					}
				});
			});
	}

	get_page_to_show() {
		let default_page;

		if (
			localStorage.current_page &&
			this.workspaces.filter((page) => page.name == localStorage.current_page).length != 0
		) {
			default_page = {
				name: localStorage.current_page,
				public: localStorage.is_current_page_public != "false",
			};
		} else if (Object.keys(this.workspaces).length !== 0) {
			default_page = {
				name: this.workspaces[0].name,
				public: this.workspaces[0].public,
			};
		} else {
			default_page = { name: "Build", public: true };
		}

		const route = frappe.get_route();
		const page = (route[1] == "private" ? route[2] : route[1]) || default_page.name;
		const is_public = route[1] ? route[1] != "private" : default_page.public;

		return { name: page, public: is_public };
	}

	async show_page(page) {
		if (!this.body.find("#editorjs")[0]) {
			$(`
				<div id="editorjs" class="desk-page page-main-content"></div>
			`).appendTo(this.body.find(".editor-js-container"));
		}

		if (this.workspaces.length) {
			this.create_page_skeleton();

			let current_page = this.workspaces.find((p) => p.name == page.name);
			this._page = current_page;
			const me = this;
			// private workspaces are stored as `${title}-${for_user}`; show just the title
			let header_dropdown = `${__(this._page.title)}`;
			frappe.breadcrumbs.add({
				type: "Custom",
				label: header_dropdown,
				route: "#",
			});
			if (!this.add_workspace_controls) {
				this.workspace_actions_button = this.page.add_action_icon("ellipsis", "", "");

				$(this.workspace_actions_button).removeAttr("data-original-title");
				$(this.workspace_actions_button).removeClass("btn-default");
				frappe.ui.create_menu({
					parent: $(this.workspace_actions_button),
					open_on_left: true,
					size: "fit-content",
					menu_items: [
						{
							label: "Edit",
							icon: "pencil",
							onClick: async () => {
								if (!this.editor || !this.editor.readOnly) return;
								this.is_read_only = false;
								await this.editor.readOnly.toggle();
								this.editor.isReady.then(() => {
									this.setup_customization_buttons(this._page);
									this.make_blocks_sortable();
								});
							},
							condition: () => {
								return current_page.is_editable;
							},
						},
						{
							label: "New",
							icon: "plus",
							onClick: () => this.initialize_new_page(),
							condition: () => {
								return this.has_create_access;
							},
						},
						{
							label: "Manage",
							icon: "settings",
							onClick: () => this.open_workspace_manager(current_page),
							condition: () => {
								// available whenever the user can manage at least one workspace
								// (a Workspace Manager, or anyone with their own private pages)
								return this.workspaces.some((p) => p.is_editable);
							},
						},
						{
							label: "Reset to Standard",
							icon: "rotate-ccw",
							onClick: () => this.reset_workspace_customization(current_page),
							condition: () => {
								return current_page.is_customized && this.has_access;
							},
						},
					],
				});
				this.add_workspace_controls = true;
			}

			this.wrapper.find(".workspace-header").hide();
			this.wrapper
				.find(".editor-js-container")
				.get(0)
				.style.setProperty("margin-top", "var(--margin-sm)");

			// set app
			let app;
			if (!this._page.public) {
				app = "private";
			} else {
				// derived from the module -- there is no `Workspace.app` any more
				app =
					(this._page.module &&
						frappe.boot.module_app[frappe.router.slug(this._page.module)]) ||
					"frappe";
			}

			parse_content(current_page);

			this.content = current_page.content;
			this.content && this.add_custom_cards_in_content();
			this.content && this.add_hidden_notice_in_content(current_page);
			this.add_mount_notice(current_page);

			$(".item-anchor").addClass("disable-click");

			if (this.pages && this.pages[current_page.name]) {
				this.page_data = this.pages[current_page.name];
			} else {
				await frappe.after_ajax(() => this.get_data(current_page));
			}

			this.setup_actions(page);

			this.prepare_editorjs();
			$(".item-anchor").removeClass("disable-click");

			this.remove_page_skeleton();
			this.wrapper.find(".workspace-title").html(__(this._page.title));
			this.wrapper
				.find(".workspace-icon")
				.html(frappe.utils.icon(this._page.icon || "folder", "md"));

			localStorage.current_page = current_page.name;
			localStorage.is_current_page_public = current_page.public ? "true" : "false";
		}
	}

	add_custom_cards_in_content() {
		let index = -1;
		this.content.find((item, i) => {
			if (item.type == "card") index = i;
		});
		if (index !== -1) {
			this.content.splice(index + 1, 0, {
				type: "card",
				data: { card_name: "Custom Documents", col: 4 },
			});
			this.content.splice(index + 2, 0, {
				type: "card",
				data: { card_name: "Custom Reports", col: 4 },
			});
		}
	}

	prepare_editorjs() {
		if (this.editor) {
			this.editor.isReady.then(() => {
				this.editor.configuration.tools.chart.config.page_data = this.page_data;
				this.editor.configuration.tools.shortcut.config.page_data = this.page_data;
				this.editor.configuration.tools.card.config.page_data = this.page_data;
				// this.editor.configuration.tools.onboarding.config.page_data = this.page_data;
				this.editor.configuration.tools.quick_list.config.page_data = this.page_data;
				this.editor.configuration.tools.number_card.config.page_data = this.page_data;
				this.editor.configuration.tools.custom_block.config.page_data = this.page_data;
				this.editor.render({ blocks: this.content || [] });
			});
		} else {
			this.initialize_editorjs(this.content);
		}
	}

	setup_actions(page) {
		let current_page = this.workspaces.filter((p) => p.name == page.name)[0];

		if (!this.is_read_only) {
			this.setup_customization_buttons(current_page);
			return;
		}

		this.clear_page_actions();
		if (current_page.is_editable) {
			this.body.find(".btn-edit-workspace").removeClass("hide");
		} else {
			this.body.find(".btn-edit-workspace").addClass("hide");
		}
		// need to add option for icons in inner buttons as well
		if (this.has_create_access) {
			this.body.find(".btn-new-workspace").removeClass("hide");
		} else {
			this.body.find(".btn-new-workspace").addClass("hide");
		}
	}

	add_hidden_notice_in_content(page) {
		// A hidden workspace is dropped from everyone else's sidebar; a Workspace Manager
		// still sees it. Prepend a display-only text block explaining why. The sentinel
		// span lets save_page() strip it so it is never persisted into the workspace.
		if (!page.is_hidden || !this.has_access) return;
		if (
			this.content.some(
				(b) => b.type == "paragraph" && b.data?.text?.includes(HIDDEN_NOTICE_MARKER)
			)
		) {
			return;
		}
		this.content.unshift({
			type: "paragraph",
			data: {
				text: `<span class="${HIDDEN_NOTICE_MARKER}">${__(
					"This workspace is hidden from other users. You can see it because you're a Workspace Manager."
				)}</span>`,
				col: "12",
			},
		});
	}

	// A workspace with no `app` is in no app's sidebar, so it's only reachable through global
	// search or Manage Workspaces. Prompt whoever lands on it: a dialog offering to place it for
	// anyone who can, and an explanation for anyone who can't. Both are dismissible -- being
	// unmounted is worth raising, but not worth trapping someone over.
	async add_mount_notice(page) {
		// standard workspaces are mounted by the app that ships them, via their module
		if (!page || page.module || page.standard || page.type !== "Workspace") return;
		// show_page runs on every navigation -- don't stack dialogs on the same workspace
		if (this.mount_dialog && this.mount_dialog.page_name === page.name) return;
		// ...and once it's been waved off, leave it alone for the rest of the session rather
		// than re-asking every time the workspace is opened
		if (this.dismissed_mount_prompts?.has(page.name)) return;

		// mirrors `can_edit_workspace` on the server: a Workspace Manager may mount anything,
		// anyone may mount their own private workspace
		const can_mount =
			this.has_access || (!page.public && page.for_user === frappe.session.user);

		if (!can_mount) {
			// there's nothing for them to act on, so say it once and don't raise it again
			this.dismissed_mount_prompts = this.dismissed_mount_prompts || new Set();
			this.dismissed_mount_prompts.add(page.name);
			frappe.msgprint({
				title: __("Not in any app"),
				indicator: "orange",
				message: __(
					"This workspace isn't in any app's sidebar, so it can only be found through search. Ask a Workspace Manager to add it to an app."
				),
			});
			return;
		}

		await this.prompt_assign_module(page);
	}

	// Ask which module `page` belongs to, then assign it and refresh the desk in place. Closing
	// the dialog without choosing is fine -- it just won't ask again this session.
	async prompt_assign_module(page) {
		const modules = await this.get_assignable_modules();
		let mounted = false;
		const d = new frappe.ui.Dialog({
			title: __("Add {0} to a module", [__(page.title)]),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "why",
					options: `<p class="text-muted">${__(
						"This workspace isn't in any module's sidebar yet, so there's no way to navigate to it. Pick the module it belongs to."
					)}</p>`,
				},
				{
					label: __("Module"),
					fieldtype: "Select",
					fieldname: "module",
					reqd: 1,
					options: this.module_select_options(modules),
					default: frappe.app.sidebar?.current_module_def(),
					description: __("Which module's sidebar this workspace appears in"),
				},
			],
			primary_action_label: __("Add"),
			primary_action: (values) => {
				mounted = true;
				d.hide();
				frappe.call({
					method: "frappe.desk.doctype.workspace.workspace.set_workspace_module",
					args: { name: page.name, module: values.module },
					freeze: true,
					callback: (r) => {
						if (!r.message) return;
						this.apply_manager_changes(r.message);
						frappe.show_alert({
							message: __("Added {0} to {1}", [__(page.title), __(values.module)]),
							indicator: "green",
						});
					},
				});
			},
		});

		// tracked so a re-render of the same workspace doesn't stack a second copy on top
		d.page_name = page.name;
		this.mount_dialog = d;
		d.$wrapper.on("hidden.bs.modal", () => {
			if (this.mount_dialog === d) this.mount_dialog = null;
			// closed without picking an app -> take the hint and stop asking for this session
			if (!mounted) {
				this.dismissed_mount_prompts = this.dismissed_mount_prompts || new Set();
				this.dismissed_mount_prompts.add(page.name);
			}
		});

		d.show();
	}

	async open_workspace_manager(current_page) {
		// Two-pane manager, shaped like the schema it manages: **modules** on the left, and the
		// selected module's workspaces listed on the right. A workspace's module is what decides
		// which dock lists it and whose sidebar carries it, so moving one between modules is the
		// management task -- which makes the module, not the workspace, the thing to organise by.
		// The old rail listed every workspace under Standard / Custom / Private, three groups
		// that say nothing about where a workspace appears.
		//
		// The list comes from the server, not `frappe.boot.workspaces`: the bootinfo only
		// carries the user's *own* private workspaces, but a Workspace Manager manages every
		// workspace (including other users' private ones).
		// `EmbeddedList` is a lazy bundle rather than part of the desk one, so it has to be here
		// before a module panel renders. Loaded alongside the two reads rather than after them,
		// and awaited as one so the first panel builds synchronously when the dialog opens.
		const [manageable, modules] = await Promise.all([
			frappe.xcall("frappe.desk.doctype.workspace.workspace.get_manageable_workspaces"),
			this.get_assignable_modules(),
			frappe.require("embedded_list.bundle.js").catch((e) => {
				// eslint-disable-next-line no-console
				console.error("Manage Workspaces: failed to load embedded_list.bundle.js", e);
				frappe.ui.toast({
					message: __("The workspace list may not load. Please refresh the page."),
					type: "warning",
				});
			}),
		]);
		if (!manageable || !manageable.length) return;

		this.manager_modules = modules;
		const tabs = this.workspace_manager_tabs(manageable, modules);

		this.workspace_manager = new frappe.ui.SettingsDialog({
			title: __("Manage Workspaces"),
			tabs,
			default_tab: this.manager_tab_for(tabs, current_page && current_page.module),
		});
		this.workspace_manager.show();
	}

	// One rail item per module that holds something, in a single flat list. Deliberately not
	// every module on the site: the rail is how you *find* a workspace, and moving one into a
	// module that holds none is the Module field's job, which offers the full list.
	//
	// The rail is not grouped by app. The dialog manages modules, and which app happens to ship
	// a module isn't something you act on here -- app headings only broke one short list into
	// several shorter ones and pushed the modules themselves down the page.
	workspace_manager_tabs(manageable, modules) {
		const meta = {};
		(modules || []).forEach((m) => (meta[m.module] = m));

		const by_module = new Map();
		manageable.forEach((page) => {
			page._access = page.standard
				? __("Standard")
				: page.public
				? __("Everyone")
				: page.for_user
				? __("Private")
				: __("Shared");
			const key = page.module || "";
			if (!by_module.has(key)) by_module.set(key, []);
			by_module.get(key).push(page);
		});

		// The unreachable ones lead, because they're the ones worth triaging. Two states share
		// that top: a workspace with no module at all, and one naming a module that isn't there
		// -- a `Link` the database doesn't enforce, so a module can be renamed or deleted out
		// from under one. Both are equally unreachable and both are fixed the same way, by the
		// Module field. Everything else is plain alphabetical: with no headings to scan, the
		// label is what you look for.
		const missing = (key) => Boolean(key) && !meta[key];
		const rank = (key) => (!key || missing(key) ? 0 : 1);

		const keys = [...by_module.keys()].sort((a, b) => {
			const al = (meta[a] || {}).label || a;
			const bl = (meta[b] || {}).label || b;
			return rank(a) - rank(b) || __(al).localeCompare(__(bl));
		});

		const items = keys.map((key) => {
			// A workspace whose module can't be offered still has to appear, or it would drop
			// out of the only dialog that can move it. `missing` also covers a module this
			// particular user may not see (a block hides it), which is a different cause with
			// the same consequence for them: they cannot navigate to it.
			const module = meta[key] || {
				module: key,
				label: key || __("No module"),
				app_title: null,
				missing: Boolean(key),
			};
			return {
				id: key || NO_MODULE_TAB,
				label: __(module.label),
				// icon: module.missing || !key ? "circle-alert" : "folder",
				render: (panel) => this.render_module_panel(panel, module, by_module.get(key)),
			};
		});

		// One group, so the rail carries a single top-level heading naming what the list is
		// instead of a heading per app splitting it into pieces.
		return [{ group: __("Modules"), items }];
	}

	// `SettingsDialog.activate` silently does nothing for an id it has no item for, which would
	// leave the dialog open on a blank panel -- so a module is only offered as the landing tab
	// once it's confirmed to be one.
	manager_tab_for(tabs, module) {
		const wanted = module || NO_MODULE_TAB;
		const found = tabs.some((group) => group.items.some((item) => item.id === wanted));
		return found ? wanted : undefined;
	}

	// A module's workspaces. The list and the per-workspace form are two views of the *same*
	// panel (`set_view` swaps it whole, `refresh()` restores the list), so drilling in doesn't
	// stack a second dialog over the first.
	render_module_panel(panel, module, pages) {
		const rows = pages || [];
		panel.set_view({
			title: __(module.label),
			render: (p) => {
				new frappe.ui.EmbeddedList({
					wrapper: $('<div class="workspace-manager-list"></div>').appendTo(p.body),
					// The line belongs to the list rather than the panel header above it: the
					// list draws no header at all without a title, description or Add button,
					// and the search box rides in that header -- so a bare list silently loses
					// the one control a long module needs.
					description: module.missing
						? __(
								"{0} workspace(s) name the module {1}, which doesn't exist on this site — nothing can navigate to them. Give each one a module below.",
								[rows.length, module.module]
						  )
						: !module.module
						? __(
								"{0} workspace(s) have no module, so nothing can navigate to them. Give each one a module below.",
								[rows.length]
						  )
						: module.app_title
						? __("{0} workspace(s) in this module, which {1} ships.", [
								rows.length,
								__(module.app_title),
						  ])
						: __("{0} workspace(s) in this module, which this site owns.", [
								rows.length,
						  ]),
					empty_message: __("No workspaces in this module."),
					empty_icon: "layout-grid",
					get_data: () => Promise.resolve(rows),
					on_row_click: (row) => this.open_workspace_settings(panel, row),
					columns: [
						{
							label: __("Workspace"),
							fieldname: "title",
							render: (row) => frappe.utils.escape_html(__(row.title)),
						},
						{
							label: __("Access"),
							fieldname: "_access",
							type: "badge",
							color: (row) =>
								row.standard ? "blue" : row.public ? "green" : "gray",
						},
						// a manager sees private workspaces owned by other people -- whose they
						// are is the column that tells them apart, since the titles won't
						{ label: __("Owner"), fieldname: "for_user" },
					],
				}).refresh();
			},
		});
	}

	// The selected workspace's settings, in place of the list.
	async open_workspace_settings(panel, page) {
		panel.set_view({
			title: __(page.title),
			render: (p) => p.body.html(`<div class="text-muted">${__("Loading...")}</div>`),
		});

		const settings = await frappe.xcall(
			"frappe.desk.doctype.workspace.workspace.get_workspace_settings",
			{ name: page.name }
		);
		if (!settings) return;

		// Back before anything destructive, and it returns to the list rather than closing:
		// sorting a module's workspaces means going in and out of this view repeatedly.
		const actions = [
			{ label: __("Back"), icon: "chevron-left", click: () => panel.refresh() },
		];
		if (!settings.standard) {
			actions.push({
				label: __("Delete"),
				theme: "red",
				click: () => this.delete_workspace_from_manager(page),
			});
		}
		actions.push({
			label: __("Save"),
			variant: "solid",
			click: (p) => this.save_workspace_from_manager(p, settings),
		});

		panel.set_view({
			title: __(settings.title),
			description: settings.standard
				? __(
						"A standard workspace is shipped by the app; changes are saved as customizations."
				  )
				: __("Control who can see this workspace and how it appears."),
			actions,
			fields: this.workspace_manager_fields(settings, this.manager_modules),
		});
	}

	// Rebuild the rail after a change that can move a workspace between modules, and land on
	// whichever module it went to -- watching it arrive is the point of doing this here.
	async refresh_workspace_manager(module) {
		if (!this.workspace_manager) return;

		const manageable = await frappe.xcall(
			"frappe.desk.doctype.workspace.workspace.get_manageable_workspaces"
		);
		if (!manageable || !manageable.length) {
			this.workspace_manager.hide();
			return;
		}

		const tabs = this.workspace_manager_tabs(manageable, this.manager_modules);
		this.workspace_manager.reset(tabs, this.manager_tab_for(tabs, module));
	}

	workspace_manager_fields(settings, apps) {
		const access_to_label = {
			private: ACCESS_PRIVATE,
			group: ACCESS_GROUP,
			public: ACCESS_PUBLIC,
		};
		// A standard workspace's `public` flag is app-owned, so it can only ever be shared
		// (open to everyone or gated to a group). Custom workspaces get the full range, but
		// only a Workspace Manager may make one public.
		let access_options;
		if (settings.standard) {
			access_options = [ACCESS_GROUP, ACCESS_PUBLIC];
		} else if (this.has_access) {
			access_options = [ACCESS_PRIVATE, ACCESS_GROUP, ACCESS_PUBLIC];
		} else {
			access_options = [ACCESS_PRIVATE];
		}

		const role_rows = (settings.roles || []).map((role) => ({ role }));

		return [
			{
				label: __("Title"),
				fieldname: "title",
				fieldtype: "Data",
				default: settings.title,
				reqd: 1,
				read_only: settings.standard ? 1 : 0,
				description: settings.standard
					? __("The title of a standard workspace is managed by the app.")
					: "",
			},
			{
				label: __("Module"),
				fieldname: "module",
				fieldtype: "Select",
				options: this.module_select_options(apps || []),
				default: settings.module,
				// a standard workspace's module is owned by the app that ships it, and there's
				// no per-site override to record a different one in
				read_only: settings.standard ? 1 : 0,
				description: settings.standard
					? __("A standard workspace stays in the module that ships it.")
					: __("Which module's sidebar this workspace appears in"),
			},
			{
				label: __("Icon"),
				fieldname: "icon",
				fieldtype: "Icon",
				default: settings.icon,
			},
			{
				label: __("Access"),
				fieldname: "access",
				fieldtype: "Select",
				options: access_options,
				default: access_to_label[settings.access] || access_options[0],
				reqd: 1,
				description: __("Who can see this workspace"),
			},
			{
				label: __("Roles"),
				fieldname: "roles",
				fieldtype: "Table",
				depends_on: `eval:doc.access=='${ACCESS_GROUP}'`,
				description: __("Users with any of these roles can see this workspace"),
				data: role_rows,
				get_data: () => role_rows,
				fields: [
					{
						label: __("Role"),
						fieldname: "role",
						fieldtype: "Link",
						options: "Role",
						in_list_view: 1,
						reqd: 1,
					},
				],
			},
		];
	}

	save_workspace_from_manager(panel, settings) {
		const values = panel.get_values();
		if (!values) return;

		const label_to_access = {
			[ACCESS_PRIVATE]: "private",
			[ACCESS_GROUP]: "group",
			[ACCESS_PUBLIC]: "public",
		};
		const access = label_to_access[values.access];
		const roles =
			access === "group" ? (values.roles || []).map((r) => r.role).filter(Boolean) : [];

		frappe.call({
			method: "frappe.desk.doctype.workspace.workspace.update_workspace_settings",
			args: {
				name: settings.name,
				title: values.title,
				icon: values.icon,
				access,
				roles,
				// read-only for standard workspaces, so this only ever moves a custom one
				module: values.module,
			},
			freeze: true,
			callback: (r) => {
				if (!r.message) return;
				this.apply_manager_changes(r.message);
				frappe.show_alert({ message: __("Workspace updated"), indicator: "green" });
				// Stay open on the module it now belongs to. Saving used to close the dialog,
				// which made moving several workspaces a matter of reopening it each time --
				// and left the one thing worth seeing, where it landed, unshown.
				this.refresh_workspace_manager(values.module || settings.module);
			},
		});
	}

	delete_workspace_from_manager(page) {
		frappe.confirm(
			__("Delete the <b>{0}</b> workspace? This cannot be undone.", [__(page.title)]),
			() => {
				frappe.call({
					method: "frappe.desk.doctype.workspace.workspace.delete_page",
					args: { name: page.name },
					freeze: true,
					callback: (r) => {
						if (!r.message) return;
						this.apply_manager_changes(r.message);
						frappe.show_alert({
							message: __("Workspace {0} deleted", [__(page.title)]),
							indicator: "green",
						});
						// back to the module it was in, which is where the next one to look at is
						this.refresh_workspace_manager(page.module);
					},
				});
			}
		);
	}

	apply_manager_changes(message) {
		// Refresh the cached workspace + sidebar payloads and re-render, mirroring create_page.
		frappe.boot.workspaces = message.workspace_pages;
		this.workspaces = frappe.boot.workspaces.pages;
		this.setup_pages(frappe.boot.workspaces.pages);
		if (message.module_sidebars) frappe.boot.module_sidebars = message.module_sidebars;
		if (message.entity_module) frappe.boot.entity_module = message.entity_module;
		// The dock is app-scoped: it renders `app_data[app].dock`. A workspace that just changed
		// app (or gained one) only moves docks once this mapping is swapped in.
		if (message.app_data) frappe.boot.app_data = message.app_data;
		this.reload();
		// reload() re-derives the current page synchronously; re-render its sidebar so a rename
		// or visibility change is reflected in the shell.
		if (frappe.app.sidebar && this._page) {
			frappe.app.sidebar.setup(this._page.name);
			// ...and re-resolve the app context + dock, which `setup` leaves alone
			frappe.app.sidebar.refresh();
		}
	}

	reset_workspace_customization(page) {
		frappe.confirm(
			__(
				"Reset <b>{0}</b> to the standard, app-shipped version? This removes all site customizations.",
				[__(page.title)]
			),
			() => {
				frappe.call({
					method: "frappe.desk.doctype.custom_workspace.custom_workspace.reset_workspace_customization",
					args: { workspace: page.name },
					freeze: true,
					callback: () => {
						// back on the app's layout, so the next layout save freezes it
						// afresh and is worth warning about again
						page.is_layout_customized = 0;
						frappe.show_alert({
							message: __("Workspace reset to standard"),
							indicator: "green",
						});
						this.reload();
					},
				});
			}
		);
	}

	initialize_editorjs_undo() {
		this.undo = new Undo({ editor: this.editor });
		this.undo.initialize({ blocks: this.content || [] });
		this.undo.readOnly = false;
	}

	clear_page_actions() {
		this.page.clear_primary_action();
		this.page.clear_secondary_action();
		this.page.clear_inner_toolbar();

		// switch headers
		if (!this.body.hasClass("edit-mode")) {
			this.wrapper.find(".workspace-header").removeClass("hidden");
		}
	}

	setup_customization_buttons(page) {
		this.body.addClass("edit-mode");
		this.initialize_editorjs_undo();
		this.clear_page_actions();
		$("#full-search-button").addClass("hidden");

		// switch headers
		this.wrapper.find(".page-head").removeClass("hidden");
		this.wrapper.find(".workspace-header").addClass("hidden");

		page.is_editable &&
			this.page.set_primary_action(
				__("Save"),
				() => {
					// a standard workspace's first layout save freezes it against app
					// updates, so it is confirmed before it happens, not reported after
					this.confirm_layout_freeze(page).then((go_ahead) => {
						if (!go_ahead) return;
						this.clear_page_actions();
						this.body.removeClass("edit-mode");
						$("#full-search-button").removeClass("hidden");
						this.save_page(page).then((saved) => {
							if (!saved) return;
							this.undo.readOnly = true;
							this.editor.readOnly.toggle();
							this.is_read_only = true;
						});
					});
				},
				null,
				__("Saving")
			);

		this.page.set_secondary_action(__("Discard"), async () => {
			this.body.removeClass("edit-mode");
			this.clear_page_actions();
			$("#full-search-button").removeClass("hidden");
			await this.editor.readOnly.toggle();
			this.is_read_only = true;
			frappe.boot.workspaces = this.cached_pages;
			this.reload();
			frappe.show_alert({ message: __("Customizations Discarded"), indicator: "info" });
		});

		if (page.name && this.has_access) {
			this.page.add_inner_button(__("Settings"), () => {
				frappe.set_route(`workspace/${page.name}`);
			});
		}
		$(this.workspace_actions_button).remove();
		this.add_workspace_controls = false;
	}

	// A standard workspace's layout is stored as a *snapshot*, so saving one stops the app's
	// later layout changes from reaching this site -- while its roles, icon and visibility
	// keep updating, because those are stored as a diff. Say so at the point the user causes
	// it. Only the first time: once the snapshot exists there is nothing left to warn about.
	confirm_layout_freeze(page) {
		const freezes = page.standard && !page.is_layout_customized && !frappe.boot.developer_mode;
		if (!freezes) return Promise.resolve(true);

		return new Promise((resolve) => {
			frappe.confirm(
				__(
					"<b>{0}</b> is shipped by its app. Saving this layout keeps your arrangement, and the app's later changes to this page's layout will stop showing up here. Its roles, icon and visibility keep following the app either way, and <b>Reset to Standard</b> undoes this.",
					[__(page.title)]
				),
				() => resolve(true),
				() => resolve(false),
				__("Save Layout"),
				__("Cancel")
			);
		});
	}

	make_blocks_sortable() {
		let me = this;
		this.page_sortable = Sortable.create(
			this.page.main.find(".codex-editor__redactor").get(0),
			{
				handle: ".drag-handle",
				draggable: ".ce-block",
				animation: 150,
				onEnd: function (evt) {
					me.editor.blocks.move(evt.newIndex, evt.oldIndex);
				},
				setData: function () {
					//Do Nothing
				},
			}
		);
	}

	async initialize_new_page() {
		var me = this;
		this.get_parent_pages();
		// A workspace with no module lands on no dock, so ask for it up front rather than let
		// the workspace be created stranded and rely on the "not on any dock" prompt to rescue it.
		const apps = await this.get_assignable_modules();
		const d = new frappe.ui.Dialog({
			title: __("New Workspace"),
			fields: [
				{
					label: __("Title"),
					fieldtype: "Data",
					fieldname: "title",
					reqd: 1,
				},
				{
					label: __("Type"),
					fieldtype: "Select",
					fieldname: "type",
					options: ["Workspace", "Link", "URL"],
					default: "Workspace",
					reqd: 1,
					onchange: function () {
						d.set_df_property("link_type", "hidden", this.get_value() != "Link");
						d.set_df_property("link_to", "hidden", this.get_value() != "Link");
					},
				},
				{
					label: __("Link Type"),
					depends_on: `eval:doc.type=='Link'`,
					mandatory_depends_on: `eval:doc.type=='Link'`,
					fieldtype: "Select",
					fieldname: "link_type",
					options: ["DocType", "Page", "Report"],
				},
				{
					label: __("Link To"),
					depends_on: `eval:doc.type=='Link'`,
					mandatory_depends_on: `eval:doc.type=='Link'`,
					fieldtype: "Dynamic Link",
					fieldname: "link_to",
					options: "link_type",
				},
				{
					label: __("External Link"),
					depends_on: `eval:doc.type=='URL'`,
					mandatory_depends_on: `eval:doc.type=='URL'`,
					fieldtype: "Data",
					fieldname: "external_link",
					options: "URL",
				},
				{
					label: __("Access"),
					fieldtype: "Select",
					fieldname: "access",
					reqd: 1,
					default: ACCESS_PRIVATE,
					options: this.access_options(),
					description: __("Who can see this workspace"),
					onchange: function () {
						let is_private = this.get_value() === ACCESS_PRIVATE;
						d.set_df_property(
							"parent",
							"options",
							is_private ? me.private_parent_pages : me.public_parent_pages
						);
						d.set_df_property(
							"roles",
							"hidden",
							this.get_value() !== ACCESS_GROUP ? 1 : 0
						);
					},
				},
				{
					label: __("Module"),
					fieldtype: "Select",
					fieldname: "module",
					reqd: 1,
					options: this.module_select_options(apps),
					default: frappe.app.sidebar?.current_module_def(),
					description: __("Which module's sidebar this workspace appears in"),
				},
				{
					label: __("Icon"),
					fieldtype: "Icon",
					fieldname: "icon",
				},
				{
					label: __("Roles"),
					fieldtype: "Table",
					fieldname: "roles",
					hidden: 1,
					description: __("Users with any of these roles can see this workspace"),
					fields: [
						{
							label: __("Role"),
							fieldtype: "Link",
							fieldname: "role",
							options: "Role",
							in_list_view: 1,
							reqd: 1,
						},
					],
				},
				{
					label: __("Parent"),
					fieldtype: "Select",
					fieldname: "parent",
					options: this.private_parent_pages,
					hidden: 1,
				},
			],
			primary_action_label: __("Create"),
			primary_action: (values) => {
				values.title = strip_html(values.title);
				d.hide();

				let is_public = values.access !== ACCESS_PRIVATE;
				let name = values.title + (is_public ? "" : "-" + frappe.session.user);
				// seed the new workspace with the welcome blocks (header + edit hint) so it opens
				// with guidance instead of a bare title
				let blocks = [
					{
						type: "header",
						data: { text: __("Welcome to the {0} workspace", [values.title]) },
					},
				];
				if (this.has_access) {
					blocks.push({
						type: "paragraph",
						data: {
							// plain text, never markup: `content` is a Long Text field, so a tag
							// with an attribute in it is HTML-sanitized on save and comes back
							// with the JSON's own quotes rewritten -- i.e. unparseable content.
							text: __("Click on the {0} menu to edit", ["\u22ef"]),
						},
					});
				}

				let new_page = {
					content: JSON.stringify(blocks),
					name: name,
					label: name,
					title: values.title,
					public: is_public ? 1 : 0,
					for_user: is_public ? "" : frappe.session.user,
					icon: values.icon,
					roles: values.access === ACCESS_GROUP ? values.roles || [] : [],
					parent_page: values.parent || "",
					// the module this workspace belongs to -- it decides the dock entry it
					// appears under, and defaults to the module of the shell it was created from
					module: values.module || frappe.app.sidebar?.current_module_def(),
					is_editable: true,
					selected: true,
					type: values.type,
					link_type: values.link_type,
					link_to: values.link_to,
					external_link: values.external_link,
				};

				if (new_page.type !== "Workspace") {
					this.create_page(new_page);
				} else {
					// Create then navigate to the new workspace in view (read-only) mode. We don't
					// set up the edit-mode customization buttons or toggle the editor here -- the
					// route change re-renders the workspace read-only.
					this.create_page(new_page).then(() => {
						let route = frappe.router.slug(
							new_page.public ? new_page.name : "private/" + new_page.name
						);
						frappe.set_route(route);
					});
				}
			},
		});
		d.show();
	}

	create_page(new_page) {
		const me = this;
		return new Promise((resolve) => {
			frappe.call({
				method: "frappe.desk.doctype.workspace.workspace.new_page",
				args: {
					new_page: new_page,
				},
				callback: (r) => {
					if (r.message) {
						let message = __("Workspace {0} created", [new_page.title.bold()]);
						if (!window.Cypress) {
							frappe.show_alert({
								message: message,
								indicator: "green",
							});
						}
						if (r.message) {
							frappe.boot.workspaces = r.message.workspace_pages;
							me.workspaces = frappe.boot.workspaces.pages;
							me.setup_pages(frappe.boot.workspaces.pages);
							if (r.message.module_sidebars)
								frappe.boot.module_sidebars = r.message.module_sidebars;
							if (r.message.entity_module)
								frappe.boot.entity_module = r.message.entity_module;
						}

						// Switch the shell to the module the new workspace belongs to, so it
						// reflects the just-created workspace. Nothing is pushed onto the rail:
						// the rail lists the entries an app's `Dock` record names
						// names, and a new workspace reaches the shell through its module's
						// sidebar instead.
						const module = frappe.app.sidebar.module_for_workspace(new_page.name);
						if (module) {
							frappe.app.sidebar.setup(module);
						}

						resolve();
					}
				},
			});
		});
	}

	setup_pages(all_pages) {
		all_pages.forEach((page) => {
			page.is_editable = !page.public || this.has_access;
			parse_content(page);
		});

		if (all_pages) {
			frappe.workspaces = {};
			frappe.workspace_list = [];
			frappe.workspace_map = {};
			for (let page of all_pages) {
				// `app` is derived, not stored -- consumers still read it off the page object
				if (page.module) {
					page.app = frappe.boot.module_app[frappe.slug(page.module)];
				}
				// store the full page (matching desk.js setup_workspaces) so consumers like the
				// sidebar header have title/icon/for_user, not just name/public
				frappe.workspaces[frappe.router.slug(page.name)] = page;
				frappe.workspace_map[page.name] = page;
				frappe.workspace_list.push(page);
			}
		}
	}
	initialize_editorjs(blocks) {
		this.tools = {
			header: {
				class: this.blocks["header"],
				inlineToolbar: ["HeaderSize", "bold", "italic", "link"],
				config: {
					default_size: 4,
				},
			},
			paragraph: {
				class: this.blocks["paragraph"],
				inlineToolbar: ["HeaderSize", "bold", "italic", "link"],
				config: {
					placeholder: __("Choose a block or continue typing"),
				},
			},
			chart: {
				class: this.blocks["chart"],
				config: {
					page_data: this.page_data || [],
				},
			},
			card: {
				class: this.blocks["card"],
				config: {
					page_data: this.page_data || [],
				},
			},
			shortcut: {
				class: this.blocks["shortcut"],
				config: {
					page_data: this.page_data || [],
				},
			},
			onboarding: {
				class: this.blocks["onboarding"],
				config: {
					page_data: this.page_data || [],
				},
			},
			quick_list: {
				class: this.blocks["quick_list"],
				config: {
					page_data: this.page_data || [],
				},
			},
			number_card: {
				class: this.blocks["number_card"],
				config: {
					page_data: this.page_data || [],
				},
			},
			custom_block: {
				class: this.blocks["custom_block"],
				config: {
					page_data: this.page_data || [],
				},
			},
			spacer: this.blocks["spacer"],
			HeaderSize: frappe.workspace_block.tunes["header_size"],
		};
		this.editor = new EditorJS({
			data: {
				blocks: blocks || [],
			},
			tools: this.tools,
			autofocus: false,
			readOnly: true,
			logLevel: "ERROR",
		});
		if (blocks.length == 0) {
			let message = __("Welcome to the {0} workspace", [this.page.title]);
			let default_block = [
				{
					type: "header",
					data: { text: message },
				},
			];
			if (this.has_access) {
				default_block.push({
					type: "paragraph",
					data: {
						text: __("Click on {0} to edit", [frappe.utils.icon("ellipsis")]),
					},
				});
			}
			this.editor.isReady.then(() => {
				this.editor.render({ blocks: default_block });
			});
		}
	}

	save_page(page) {
		let me = this;
		this.current_page = { name: page.name, public: page.public };

		return this.editor
			.save()
			.then((outputData) => {
				let new_widgets = {};

				outputData.blocks.forEach((item) => {
					if (item.data.new) {
						if (!new_widgets[item.type]) {
							new_widgets[item.type] = [];
						}
						new_widgets[item.type].push(item.data.new);
						delete item.data["new"];
					}
				});

				let blocks = outputData.blocks.filter(
					(item) =>
						item.type != "card" ||
						(item.data.card_name !== "Custom Documents" &&
							item.data.card_name !== "Custom Reports")
				);

				// never persist the display-only "workspace is hidden" notice
				blocks = blocks.filter(
					(item) =>
						!(
							item.type == "paragraph" &&
							item.data?.text?.includes(HIDDEN_NOTICE_MARKER)
						)
				);

				if (
					page.content == JSON.stringify(blocks) &&
					Object.keys(new_widgets).length === 0
				) {
					frappe.show_alert({
						message: __("No changes made"),
						indicator: "warning",
					});
					return false;
				}

				this.create_page_skeleton();
				page.content = JSON.stringify(blocks);
				frappe.call({
					method: "frappe.desk.doctype.workspace.workspace.save_page",
					args: {
						name: page.name,
						public: page.public || 0,
						new_widgets: new_widgets,
						blocks: JSON.stringify(blocks),
					},
					callback: function (res) {
						if (res.message) {
							// the layout snapshot now exists, so the freeze has already
							// happened -- don't warn about it again before the next save
							page.is_layout_customized = 1;
							me.discard = true;
							me.reload();
							if (window.Cypress) return;
							frappe.show_alert({
								message: __("Saved"),
								indicator: "green",
							});
							if (page.public) {
								frappe.set_route("desk", frappe.router.slug(page.name));
							} else {
								frappe.set_route("desk", "private", frappe.router.slug(page.name));
							}
						}
					},
				});
				return true;
			})
			.catch((error) => {
				error;
				// console.log('Saving failed: ', error);
			});
	}

	reload() {
		delete this.pages[this._page.name];
		this._page = null;
		this.setup_pages(frappe.boot.workspaces.pages);
		this.show();
		if (this.undo) this.undo.readOnly = true;
	}

	get_parent_pages(page) {
		this.public_parent_pages = [
			"",
			...this.workspaces
				.filter((p) => p.public && !p.parent_page)
				.map((p) => {
					return { label: p.title, value: p.name };
				}),
		];
		this.private_parent_pages = [
			"",
			...this.workspaces
				.filter((p) => !p.public && !p.parent_page)
				.map((p) => {
					return { label: p.title, value: p.name };
				}),
		];

		if (page) {
			return page.public ? this.public_parent_pages : this.private_parent_pages;
		}
	}

	// "Access" choices for the New Workspace dialog. Creating a public workspace (whether
	// role-gated or open to everyone) requires the Workspace Manager role, so users without
	// it can only ever create a private "Only to you" workspace.
	access_options() {
		let options = [ACCESS_PRIVATE];
		if (this.has_access) {
			options.push(ACCESS_GROUP, ACCESS_PUBLIC);
		}
		return options;
	}

	create_page_skeleton() {
		if (this.body.find(".workspace-skeleton").length) return;

		this.body.prepend(frappe.render_template("workspace_loading_skeleton"));
		this.body.find(".codex-editor").addClass("hidden");
	}

	remove_page_skeleton() {
		this.body.find(".codex-editor").removeClass("hidden");
		this.body.find(".workspace-skeleton").remove();
	}

	register_awesomebar_shortcut() {
		"abcdefghijklmnopqrstuvwxyz".split("").forEach((letter) => {
			const default_shortcut = {
				action: (e) => {
					$("#navbar-modal-search").click();
					return false; // don't prevent default = type the letter in awesomebar
				},
				page: this.page,
			};
			frappe.ui.keys.add_shortcut({ shortcut: letter, ...default_shortcut });
			frappe.ui.keys.add_shortcut({ shortcut: `shift+${letter}`, ...default_shortcut });
		});
	}
};
