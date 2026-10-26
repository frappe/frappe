// The New Workspace dialog and the renderer switch, shared by every workspace renderer.

// "Access" options: a virtual field that maps to the underlying `public`, `for_user` and `roles`.
const ACCESS_PRIVATE = __("Only to you");
const ACCESS_GROUP = __("To a group of users");
const ACCESS_PUBLIC = __("To everyone");

let assignable_modules = null;

// The modules a workspace can be assigned to. Installed modules do not change during a session.
frappe.ui.get_assignable_modules = function () {
	if (!assignable_modules) {
		assignable_modules = frappe
			.xcall("frappe.desk.doctype.workspace.workspace.get_assignable_modules")
			.then((modules) => modules || [])
			// a cached rejection would break every later caller for the rest of the session
			.catch((e) => {
				assignable_modules = null;
				throw e;
			});
	}
	return assignable_modules;
};

// Grouped by app in the label, since two apps can ship similarly named modules.
frappe.ui.workspace_module_options = function (modules) {
	return modules.map((m) => ({
		value: m.module,
		label: m.app_title ? `${__(m.label)} (${__(m.app_title)})` : __(m.label),
	}));
};

// Swap in the desk state a workspace write returns (see `workspace_payload`).
frappe.ui.update_workspace_pages = function (message) {
	frappe.boot.workspaces = message.workspace_pages;
	if (message.module_sidebars) frappe.boot.module_sidebars = message.module_sidebars;
	if (message.entity_module) frappe.boot.entity_module = message.entity_module;
	if (message.app_data) frappe.boot.app_data = message.app_data;

	const pages = frappe.boot.workspaces.pages;
	// the router resolves `/desk/private/<title>` against this list
	frappe.boot.allowed_workspaces = pages;
	frappe.workspaces = {};
	frappe.workspace_list = [];
	frappe.workspace_map = {};
	for (let page of pages) {
		if (page.module) {
			page.app = frappe.boot.module_app[frappe.slug(page.module)];
		}
		frappe.workspaces[frappe.router.slug(page.name)] = page;
		frappe.workspace_map[page.name] = page;
		frappe.workspace_list.push(page);
	}
};

// A public page is routed by its name and a private one by its title, since a private page's
// name carries its owner's email.
frappe.ui.workspace_route = function (page) {
	if (page.public) return frappe.router.slug(page.name);
	return "private/" + frappe.router.slug(page.title);
};

frappe.ui.new_workspace_dialog = async function () {
	const has_access = frappe.boot.workspaces.has_access;
	const pages = frappe.boot.workspaces.pages;
	const parent_pages = (is_public) => [
		"",
		...pages
			.filter((p) => !!p.public == is_public && !p.parent_page)
			.map((p) => ({ label: p.title, value: p.name })),
	];
	// Creating a public workspace needs the Workspace Manager role.
	const access_options = has_access
		? [ACCESS_PRIVATE, ACCESS_GROUP, ACCESS_PUBLIC]
		: [ACCESS_PRIVATE];
	// A workspace with no module lands on no dock, so ask for one up front.
	const modules = await frappe.ui.get_assignable_modules();

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
				options: access_options,
				description: __("Who can see this workspace"),
				onchange: function () {
					const is_private = this.get_value() === ACCESS_PRIVATE;
					d.set_df_property("parent", "options", parent_pages(!is_private));
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
				options: frappe.ui.workspace_module_options(modules),
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
				options: parent_pages(false),
				hidden: 1,
			},
		],
		primary_action_label: __("Create"),
		primary_action: (values) => {
			values.title = strip_html(values.title);
			d.hide();

			const is_public = values.access !== ACCESS_PRIVATE;
			const name = values.title + (is_public ? "" : "-" + frappe.session.user);
			const blocks = [
				{
					type: "header",
					data: { text: __("Welcome to the {0} workspace", [values.title]) },
				},
			];
			if (has_access) {
				blocks.push({
					type: "paragraph",
					data: {
						// Plain text, never markup: `content` is HTML-sanitized on save, which
						// rewrites the JSON's own quotes inside a tag attribute.
						text: __("Click on the {0} menu to edit", ["⋯"]),
					},
				});
			}

			const new_page = {
				content: JSON.stringify(blocks),
				name: name,
				label: name,
				title: values.title,
				public: is_public ? 1 : 0,
				for_user: is_public ? "" : frappe.session.user,
				icon: values.icon,
				roles: values.access === ACCESS_GROUP ? values.roles || [] : [],
				parent_page: values.parent || "",
				module: values.module || frappe.app.sidebar?.current_module_def(),
				type: values.type,
				link_type: values.link_type,
				link_to: values.link_to,
				external_link: values.external_link,
			};

			create_workspace(new_page).then(() => {
				if (new_page.type === "Workspace") {
					// a new workspace opens in its renderer's editor
					frappe.ui.open_workspace_editor = new_page.name;
					frappe.set_route(frappe.ui.workspace_route(new_page));
				}
			});
		},
	});
	d.show();
};

// Draw `page` with the other renderer and land in that renderer's editor at the same URL.
frappe.ui.switch_workspace_renderer = function (page, renderer) {
	return frappe
		.xcall("frappe.desk.doctype.workspace.workspace.set_workspace_renderer", {
			name: page.name,
			renderer,
		})
		.then((message) => {
			frappe.ui.update_workspace_pages(message);
			frappe.ui.open_workspace_editor = page.name;
			frappe.router.route();
		});
};

function create_workspace(new_page) {
	return frappe
		.xcall("frappe.desk.doctype.workspace.workspace.new_page", { new_page })
		.then((message) => {
			if (!message) return;
			if (!navigator.webdriver) {
				frappe.show_alert({
					message: __("Workspace {0} created", [new_page.title.bold()]),
					indicator: "green",
				});
			}
			frappe.ui.update_workspace_pages(message);

			// Switch the shell to the module the new workspace belongs to, so it shows it.
			const sidebar = frappe.app.sidebar;
			const module = new_page.public
				? sidebar.module_for_workspace(new_page.name)
				: shell_for_private_page(new_page.name);
			if (module) sidebar.setup(module);
		});
}

// A private page is listed in Private and in its module's shell. It stays in the shell on screen
// when that is one of them.
function shell_for_private_page(name) {
	const sidebar = frappe.app.sidebar;
	const shells = sidebar.get_modules_linking(name, "Workspace");
	if (shells.includes(sidebar.current_module)) return sidebar.current_module;

	return shells.find((shell) => shell !== frappe.ui.PRIVATE_SHELL) || frappe.ui.PRIVATE_SHELL;
}
