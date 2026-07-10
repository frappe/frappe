// Workspace Explorer: a card grid of an app's workspaces, reached by clicking an app on the
// desktop/apps screen (`/app/workspace-explorer/<app_name>`). Each card is a workspace the user can
// see -- its icon, title, visibility (Public/Private) and description -- and opens that workspace.
frappe.pages["workspace-explorer"].on_page_load = function (wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Workspaces"),
		single_column: true,
		hide_sidebar: true,
		workspace_dock: false,
	});
	wrapper.workspace_explorer = new WorkspaceExplorer(page);
};

frappe.pages["workspace-explorer"].on_page_show = function (wrapper) {
	wrapper.workspace_explorer.show();
};

class WorkspaceExplorer {
	constructor(page) {
		this.page = page;
		this.page.page_head.hide();
		this.$container = $('<div class="workspace-explorer">').appendTo(this.page.main);
	}

	show() {
		// route is ["workspace-explorer", "<app_name>"]; the app segment is optional
		this.app_name = frappe.get_route()[1];
		this.app = (frappe.boot.app_data || []).find((a) => a.app_name === this.app_name);
		this.render();
	}

	// Workspaces to list: the routed app's public workspaces when an app is given, otherwise every
	// workspace the user can see. Mapped to their boot metadata and de-duplicated.
	get_workspaces() {
		let names = this.app
			? this.app.workspaces || []
			: Object.values(frappe.workspaces || {}).map((ws) => ws.name);

		let seen = new Set();
		return names
			.map((name) => frappe.workspaces[frappe.router.slug(name)])
			.filter((ws) => ws && !seen.has(ws.name) && seen.add(ws.name));
	}

	render() {
		this.$container.empty();
		let heading = (this.app && this.app.app_title) || __("My Workspaces");
		let subtitle =
			(this.app && this.app.app_description) ||
			__("Switch between workspaces that you are a member of.");
		$(`
			<div class="we-header">
				<h1 class="we-title">${frappe.utils.escape_html(heading)}</h1>
				<p class="we-subtitle">${frappe.utils.escape_html(subtitle)}</p>
			</div>
		`).appendTo(this.$container);

		let workspaces = this.get_workspaces();
		if (!workspaces.length) {
			$(`<div class="we-empty text-muted">${__("No workspaces to show.")}</div>`).appendTo(
				this.$container
			);
			return;
		}

		let $grid = $('<div class="we-grid">').appendTo(this.$container);
		workspaces.forEach((ws) => $grid.append(this.card(ws)));
	}

	card(ws) {
		let title = ws.title || ws.name;
		let $card = $(`
			<a class="we-card" role="button" tabindex="0" aria-label="${frappe.utils.escape_html(title)}">
				<span class="we-card-icon">${this.icon_html(ws)}</span>
				<span class="we-card-body">
					<span class="we-card-title">${frappe.utils.escape_html(title)}</span>
					${
						ws.description
							? `<span class="we-card-desc">${frappe.utils.escape_html(
									ws.description
							  )}</span>`
							: ""
					}
				</span>
			</a>
		`);

		let open = () => this.open_workspace(ws.name);
		$card.on("click", open);
		$card.on("keydown", (e) => {
			if (e.key === "Enter" || e.key === " ") {
				e.preventDefault();
				open();
			}
		});
		return $card;
	}

	// A lucide-icon workspace gets a tile tinted by its indicator colour; icon-less ones fall back to
	// the alphabet tile used on the desktop apps screen.
	icon_html(ws) {
		if (ws.icon) {
			// a coloured tile reads white; the default gray tile keeps the icon's ink colour

			let cls = ws.indicator_color ? "we-icon-tile" : "we-icon-tile";
			return `<span class="${cls}">${frappe.utils.icon(ws.icon, "md")}</span>`;
		}
		return frappe.utils.desktop_icon(ws.title || ws.name, "gray", "lg", "Solid");
	}

	open_workspace(name) {
		// Open the workspace's own desk page (e.g. /desk/gst-india) directly, rather than jumping to
		// its first sidebar link or the legacy "Workspaces/<name>" route. Navigating to the /desk
		// route lets the sidebar's route handler select + remember the workspace and resolve the app
		// context on arrival.
		let slug = frappe.router.slug(name);
		let ws = frappe.workspaces[slug];
		frappe.set_route(ws && !ws.public ? `/desk/private/${slug}` : `/desk/${slug}`);
	}
}
