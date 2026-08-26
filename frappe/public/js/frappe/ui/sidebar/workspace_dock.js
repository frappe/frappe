// Workspace dock: a slim vertical rail rendered to the left of the body sidebar. Its top slot says
// what you are inside and links back out of it; below that it lists the modules you can switch to.
// Both come from the one question app context is still asked -- which app owns the sidebar on
// screen (Sidebar.get_sidebar_app):
//
//   placed      logo = app icon      items = the app's other modules
//   standalone  logo = module icon   items = (empty)
//
// It's always on (see Sidebar.workspace_dock_enabled), but hidden until the page on screen allows
// it (page_allows_dock -- the desktop/apps screen does not).
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
			<div class="workspace-dock-shortcuts"></div>
			<div class="workspace-dock-divider" role="separator"></div>
			<div class="workspace-dock-items"></div>
			<div class="workspace-dock-divider" role="separator"></div>
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
		this.$shortcuts = this.$dock.find(".workspace-dock-shortcuts");
		this.$items = this.$dock.find(".workspace-dock-items");
		this.$user = this.$dock.find(".workspace-dock-user");
		this.render_shortcuts();
		this.render_user();
	}

	// Icon shortcuts pinned directly under the app logo -- search and notifications, replacing the
	// page header's buttons. Declared as configuration so the set, order, and each item's tooltip
	// live in one place; render_shortcuts() turns each entry into a rail button. Every item mirrors
	// <RailItem variant="ghost">: transparent until hovered.
	//
	// Item shape:
	//   name      identifier
	//   icon      icon name passed to frappe.utils.icon
	//   label     tooltip text and accessible label
	//   css_class extra class(es) on the button (external code hooks off these)
	//   condition () => bool -- whether to render this shortcut at all
	//   badge     optional extra markup appended inside the button (e.g. a count dot)
	//   on_click  optional click handler
	//   setup     optional ($item) => {} hook run after the button is built
	get_shortcuts() {
		return [
			{
				name: "search",
				icon: "search",
				label: __("Search"),
				// AwesomeBar's delegated click handler (page.js) opens the shared search modal
				// off this class -- keep it so search still toggles from the dock.
				css_class: "navbar-modal-search-mobile",
				condition: () => frappe.boot.desk_settings.search_bar,
			},
			{
				name: "notifications",
				icon: "bell",
				label: __("Notifications"),
				// the Notifications view keeps the unread count in sync off these classes (see
				// notifications.js), and toggles the same dropdown the sidebar bell does.
				css_class: "sidebar-notification",
				condition: () => frappe.boot.desk_settings.notifications,
				badge: `<span class="notification-count hidden" aria-live="polite"></span>`,
				on_click: () => this.toggle_notifications(),
				setup: ($item) => {
					// seed the badge from boot; the Notifications view keeps it live from here on
					this.sync_notification_count(
						$item,
						frappe.boot.notification_unread_count || 0
					);
				},
			},
		];
	}

	// Render the configured shortcuts under the logo, each as an icon button with a hover tooltip.
	// Set up once (make() runs once) so handlers aren't re-bound.
	render_shortcuts() {
		if (frappe.session.user === "Guest") {
			return;
		}

		this.get_shortcuts().forEach((item) => {
			if (item.condition && !item.condition()) {
				return;
			}

			let $item = $(`<button
				class="workspace-dock-item ${item.css_class || ""}"
				title="${frappe.utils.escape_html(item.label)}"
				data-toggle="tooltip"
				data-placement="right"
				aria-label="${frappe.utils.escape_html(item.label)}"
			>
				<span class="sidebar-item-icon">${frappe.utils.icon(item.icon, "md")}</span>
				${item.badge || ""}
			</button>`);

			if (item.on_click) {
				$item.on("click", item.on_click);
			}
			if (item.setup) {
				item.setup($item);
			}
			// icon-only button -- surface its label as a hover tooltip
			$item.tooltip({ boundary: "window", container: "body", trigger: "hover" });

			this.$shortcuts.append($item);
		});
	}

	// The dock shows unread as a small dot, not a number -- just toggle it on whether any exist.
	sync_notification_count($bell, count) {
		$bell.find(".notification-count").toggleClass("hidden", count <= 0);
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
		// ...and is only displayed if the page on screen allows it (the desktop/apps screen, and
		// any page still to render, do not)
		let enabled = this.sidebar.workspace_dock_enabled() && this.sidebar.page_allows_dock();
		// drives the CSS that hides the sidebar's own user button (moved into the dock) when active
		$("body").toggleClass("workspace-dock-active", enabled);

		if (!enabled) {
			this.$dock.addClass("hidden");
			return;
		}
		this.$dock.removeClass("hidden");

		// One navigation calls this up to three times -- once from the router, and twice from
		// Sidebar.refresh() (its own call, plus the one inside apply_page_visibility). Each call
		// disposes every tooltip and rebuilds every button, so rendering unconditionally meant
		// doing that two or three times over for a rail that had not changed.
		//
		// Everything the rail draws goes into this signature -- the labels and icons as well as
		// the entries themselves, so that renaming a module's sidebar still redraws its tooltip.
		// If the signature matches, there is nothing to redraw.
		const entries = this.sidebar.collect_dock_entries(this.app);
		const signature = JSON.stringify([
			this.app ? this.app.app_name : null,
			this.sidebar.current_module,
			entries.map((entry) => [
				this.sidebar.dock_key(entry),
				entry.label,
				entry.icon,
				this.sidebar.is_active_entry(entry),
			]),
		]);
		if (signature === this.rendered) return;
		this.rendered = signature;

		this.render_logo();
		this.render_entries(entries);
	}

	// The rail's top slot: what you are inside, and the way out of it. The app's icon when the
	// module on screen is placed in one, the module's own icon when it is not -- linking the
	// desktop in both cases, so a module you entered is never a room with no door.
	//
	// There is no fallback to the first installed app's logo: no rail wears branding that has
	// nothing to do with it. Every rail now carries an icon of its own, resolved from data it
	// already holds.
	render_logo() {
		const { icon, title } = this.app ? this.app_logo() : this.module_logo();

		this.$logo.empty();
		let $link = $(
			`<a href="/desk" title="${frappe.utils.escape_html(title)}" aria-label="${__("Apps")}">
				${icon}
			</a>`
		);
		$link.on("click", (e) => {
			e.preventDefault();
			frappe.set_route("/desk");
		});
		this.$logo.append($link);
	}

	// A placed module wears its app's logo. An app declaring none gets a letter icon, matching
	// the desktop apps screen.
	app_logo() {
		const title = this.app.app_title || this.app.app_name;
		const logo_url = Array.isArray(this.app.app_logo_url)
			? this.app.app_logo_url[0]
			: this.app.app_logo_url;

		const icon = logo_url
			? `<img src="${frappe.utils.escape_html(logo_url)}" alt="${frappe.utils.escape_html(
					title
			  )}" />`
			: frappe.utils.desktop_icon(title, "gray", "sm");

		return { icon, title };
	}

	// A module belonging to no app wears its own icon. No new boot payload is needed: the module
	// sidebar the rail already reads carries both the header icon and the label.
	module_logo() {
		let sidebar = frappe.boot.module_sidebars[this.sidebar.current_module] || {};
		let label = sidebar.label || this.sidebar.current_module || __("Apps");
		return { icon: this.entry_icon(sidebar.header_icon, label), title: label };
	}

	// A dock entry's icon: the authored one, else a letter icon from its label. Shared by the top
	// slot and the items below it, so a module looks the same wherever the rail shows it and a
	// pinned workspace wears its own icon on the same terms.
	entry_icon(icon, label) {
		return icon
			? frappe.utils.icon(icon, "md")
			: frappe.utils.desktop_icon(label, "gray", "sm");
	}

	// Inside a module no app claims this renders nothing: collect_dock_entries answers with no
	// entries, and an empty items region is the right answer rather than a rail of one -- an item
	// rendered permanently active with no alternatives is a switcher that cannot switch.
	render_entries(entries = this.sidebar.collect_dock_entries(this.app)) {
		// dispose tooltips from the previous render before wiping their elements
		this.$items.find('[data-toggle="tooltip"]').tooltip("dispose");
		this.$items.empty();

		entries.forEach((entry) => {
			let $item = this.make_dock_item(entry);
			if ($item) this.$items.append($item);
		});

		// the rail is icon-only, so surface each entry's name as a hover tooltip
		this.$items.find('[data-toggle="tooltip"]').tooltip({
			boundary: "window",
			container: "body",
			trigger: "hover",
		});
	}

	// One rail button, for either kind of entry. A pinned workspace needs no markup of its own:
	// `dock_entry` resolved its label and icon out of the boot payload the same way a module's
	// come from its sidebar, so from here down the two are one thing.
	make_dock_item(entry) {
		let label = entry.label;
		if (!label) return null;
		let icon = this.entry_icon(entry.icon, label);

		let is_active = this.sidebar.is_active_entry(entry);
		let $item = $(`<button
			class="workspace-dock-item ${is_active ? "active" : ""}"
			title="${frappe.utils.escape_html(label)}"
			data-toggle="tooltip"
			data-placement="right"
			aria-label="${frappe.utils.escape_html(label)}"
			${is_active ? 'aria-current="page"' : ""}
		>${icon}</button>`);

		$item.on("click", () => this.sidebar.open_dock_entry(entry));
		return $item;
	}
};
