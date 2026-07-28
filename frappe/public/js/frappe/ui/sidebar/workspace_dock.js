// Workspace dock: a slim vertical rail rendered to the left of the body sidebar that lists the
// current app's workspaces as icons, with the app logo pinned to the corner. It's always on
// (see Sidebar.workspace_dock_enabled); only page-level opt-outs (page_hides_dock, e.g. the
// desktop/apps screen) hide it. When shown it replaces the header dropdown as the workspace switcher.
frappe.ui.WorkspaceDock = class WorkspaceDock {
	constructor(sidebar) {
		this.sidebar = sidebar;
		this.make();
	}

	make() {
		// The body is a horizontal flex row (body-sidebar-container, then main-section). Insert the
		// dock as the leftmost element so it sits to the left of the sidebar.
		this.$dock = $(`<div class="workspace-dock hidden" role="navigation" aria-label="${__(
			"Workspaces"
		)}">
			<div class="workspace-dock-logo"></div>
			<div class="workspace-dock-divider" role="separator"></div>
			<div class="workspace-dock-items"></div>
			<div class="workspace-dock-divider" role="separator"></div>
			<div class="workspace-dock-actions"></div>
			<button class="workspace-dock-user" aria-label="${__("User Menu")}"></button>
		</div>`);

		let $container = $(".body-sidebar-container");
		if ($container.length) {
			this.$dock.insertBefore($container);
		} else {
			this.$dock.prependTo("body");
		}
		// Right-edge handle: the mirror of the body sidebar's own collapse handle. While the sidebar
		// is collapsed (only the rail shows), clicking the rail's right edge reopens it. Shown only in
		// the collapsed state via CSS (body.sidebar-collapsed), so it doesn't compete with the sidebar
		// handle while expanded.
		let $resize = $(`<div class="workspace-dock-resize-handle" aria-hidden="true"></div>`);
		$resize.on("click", () => this.sidebar.open());
		this.$dock.append($resize);

		// Visible affordance for the same action, mirroring the sidebar's own .sidebar-toggle-btn --
		// same circular button on the rail's right edge, chevron pointing right since it only ever
		// expands. Like the handle, CSS keeps it to the collapsed state.
		let $expand = $(`<button
			class="expand-sidebar-link workspace-dock-toggle-btn"
			aria-label="${__("Toggle Sidebar")}"
			data-placement="right"
		>${frappe.utils.icon("chevron-right", "sm", "", "", "", true)}</button>`);
		$expand.on("click", () => this.sidebar.open());
		this.$dock.append($expand);

		this.$logo = this.$dock.find(".workspace-dock-logo");
		this.$items = this.$dock.find(".workspace-dock-items");
		this.$actions = this.$dock.find(".workspace-dock-actions");
		this.$user = this.$dock.find(".workspace-dock-user");
		this.render_search();
		this.render_notifications();
		// only reserve the actions band (and its divider spacing) if something landed in it
		this.$actions.toggleClass("hidden", this.$actions.children().length === 0);
		this.render_user();
	}

	// Global search trigger, replacing the page header's search button. It carries the
	// `navbar-modal-search-mobile` class so the AwesomeBar's delegated click handler (see
	// awesome_bar.js) opens and toggles the same search modal. Set up once (make() runs once).
	render_search() {
		if (frappe.session.user === "Guest" || !frappe.boot.desk_settings.search_bar) {
			return;
		}

		let $search = $(`<button
			class="workspace-dock-item navbar-modal-search-mobile"
			title="${__("Search")}"
			data-toggle="tooltip"
			data-placement="right"
			aria-label="${__("Search")}"
		>
			<span class="sidebar-item-icon">${frappe.utils.icon("search", "md")}</span>
		</button>`);

		$search.tooltip({ boundary: "window", container: "body", trigger: "hover" });
		this.$actions.append($search);
	}

	// Notification bell pinned above the user avatar. It carries the `sidebar-notification` /
	// `sidebar-notification-count` classes so the Notifications view keeps its unread count and
	// unseen indicator in sync here too (see notifications.js), and toggles the same dropdown panel
	// the sidebar's own bell does. Set up once (make() runs once) so the handler isn't re-bound.
	render_notifications() {
		if (frappe.session.user === "Guest" || !frappe.boot.desk_settings.notifications) {
			return;
		}

		let $bell = $(`<button
			class="workspace-dock-item sidebar-notification"
			title="${__("Notifications")}"
			data-toggle="tooltip"
			data-placement="right"
			aria-label="${__("Notifications")}"
		>
			<span class="sidebar-item-icon">${frappe.utils.icon("bell", "md")}</span>
			<span class="sidebar-notification-count hidden" aria-live="polite"></span>
		</button>`);

		$bell.on("click", () => this.toggle_notifications());
		$bell.tooltip({ boundary: "window", container: "body", trigger: "hover" });
		this.$actions.append($bell);

		// seed the badge from boot; the Notifications view keeps it live from here on
		this.sync_notification_count($bell, frappe.boot.notification_unread_count || 0);
		if (frappe.boot.notification_settings && frappe.boot.notification_settings.seen == 0) {
			$bell.find(".sidebar-item-icon").addClass("indicator blue");
		}
	}

	// The dock shows unread as a small dot, not a number -- just toggle it on whether any exist.
	sync_notification_count($bell, count) {
		$bell.find(".sidebar-notification-count").toggleClass("hidden", count <= 0);
	}

	// Toggle the shared notifications panel (lives in the sidebar), mirroring the sidebar bell.
	toggle_notifications() {
		let $wrapper = this.sidebar.wrapper;
		let $dropdown = $wrapper.find(".dropdown-notifications");
		$dropdown.toggleClass("hidden");
		if (!$dropdown.hasClass("hidden")) {
			$dropdown.trigger("show.bs.dropdown");
		}
		$wrapper.find(".dropdown-background-tasks").addClass("hidden");
	}

	// User avatar pinned to the bottom of the rail; opens the same dropdown as the sidebar's user
	// button. Set up once (make() runs once) so the menu isn't re-bound on every refresh().
	render_user() {
		this.$user.html(frappe.avatar(frappe.session.user, "avatar-medium"));
		this.sidebar.create_user_menu({ parent: this.$user, button: this.$user });
	}

	refresh() {
		// the dock belongs to the app whose body sidebar is on screen
		this.app = this.sidebar.get_sidebar_app();
		// ...unless the current page opts out (e.g. the desktop/apps screen)
		let enabled = this.sidebar.workspace_dock_enabled() && !this.sidebar.page_hides_dock();
		// drives the CSS that hides the sidebar's own user button (moved into the dock) when active
		$("body").toggleClass("workspace-dock-active", enabled);

		if (!enabled) {
			this.$dock.addClass("hidden");
			return;
		}
		this.$dock.removeClass("hidden");
		this.render_logo();
		this.render_workspaces();
	}

	// App logo pinned to the top corner of the dock; clicking it opens the apps (desktop) screen.
	render_logo() {
		let logo_url = (this.app && this.app.app_logo_url) || frappe.boot.app_data[0].app_logo_url;
		let title = (this.app && this.app.app_title) || __("Apps");

		this.$logo.empty();
		let $link = $(
			`<a href="/desk" title="${frappe.utils.escape_html(title)}" aria-label="${__("Apps")}">
				<img src="${frappe.utils.escape_html(logo_url)}" alt="${frappe.utils.escape_html(title)}" />
			</a>`
		);
		$link.on("click", (e) => {
			e.preventDefault();
			frappe.set_route("/desk");
		});
		this.$logo.append($link);
	}

	render_workspaces() {
		// dispose tooltips from the previous render before wiping their elements
		this.$items.find('[data-toggle="tooltip"]').tooltip("dispose");
		this.$items.empty();

		this.sidebar.collect_selector_workspaces(this.app).forEach((workspace) => {
			let $item = this.make_workspace_item(workspace);
			if ($item) this.$items.append($item);
		});

		// the rail is icon-only, so surface each workspace's name as a hover tooltip
		this.$items.find('[data-toggle="tooltip"]').tooltip({
			boundary: "window",
			container: "body",
			trigger: "hover",
		});
	}

	make_workspace_item(workspace) {
		let label = workspace.title || workspace.label || workspace.name;
		if (!label) return null;
		let name = workspace.name || label;
		let icon = workspace.icon
			? frappe.utils.icon(workspace.icon, "md")
			: frappe.utils.desktop_icon(label, "gray", "sm");

		let is_active = this.sidebar.is_active_workspace(workspace);
		let $item = $(`<button
			class="workspace-dock-item ${is_active ? "active" : ""}"
			title="${frappe.utils.escape_html(label)}"
			data-toggle="tooltip"
			data-placement="right"
			aria-label="${frappe.utils.escape_html(label)}"
			${is_active ? 'aria-current="page"' : ""}
		>${icon}</button>`);

		$item.on("click", () => this.sidebar.open_workspace(name));
		return $item;
	}
};
