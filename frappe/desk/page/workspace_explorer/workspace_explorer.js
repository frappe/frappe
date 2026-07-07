// Workspace Explorer: a card grid of an app's workspaces, reached by clicking an app on the
// desktop/apps screen (`/app/workspace-explorer/<app_name>`). Each card is a workspace the user can
// see -- its icon, title, visibility (Public/Private) and description -- and opens that workspace.
frappe.pages["workspace-explorer"].on_page_load = function (wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("My Workspaces"),
		single_column: true,
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
		this.render();
	}

	// Workspaces to list: the routed app's public workspaces when an app is given, otherwise every
	// workspace the user can see. Mapped to their boot metadata and de-duplicated.
	get_workspaces() {
		let app = (frappe.boot.app_data || []).find((a) => a.app_name === this.app_name);
		let names = app
			? app.workspaces || []
			: Object.values(frappe.workspaces || {}).map((ws) => ws.name);

		let seen = new Set();
		return names
			.map((name) => frappe.workspaces[frappe.router.slug(name)])
			.filter((ws) => ws && !seen.has(ws.name) && seen.add(ws.name));
	}

	render() {
		this.$container.empty();
		$(`
			<div class="we-header">
				<h1 class="we-title">${__("My Workspaces")}</h1>
				<p class="we-subtitle">${__("Switch between workspaces that you are a member of.")}</p>
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
					<span class="we-card-visibility">${ws.public ? __("Public") : __("Private")}</span>
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
			let style = ws.indicator_color ? ` style="background:${ws.indicator_color}"` : "";
			let cls = ws.indicator_color ? "we-icon-tile has-color" : "we-icon-tile";
			return `<span class="${cls}"${style}>${frappe.utils.icon(ws.icon, "md")}</span>`;
		}
		return frappe.utils.desktop_icon(ws.title || ws.name, "gray", "lg", "Solid");
	}

	open_workspace(name) {
		// let the desk sidebar switch + remember the workspace when it's available; otherwise route
		if (frappe.app && frappe.app.sidebar && frappe.app.sidebar.open_workspace) {
			frappe.app.sidebar.open_workspace(name);
		} else {
			frappe.set_route("Workspaces", frappe.router.slug(name));
		}
	}
}
