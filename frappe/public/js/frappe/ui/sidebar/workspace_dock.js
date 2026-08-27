// Workspace dock: a slim vertical rail rendered to the left of the body sidebar. Its top slot says
// what you are inside and links back out of it, and below that it lists the modules you can switch
// to. Both come from the only question app context answers: which app owns the sidebar on screen
// (Sidebar.get_sidebar_app):
//
//   placed      logo = app icon      items = the app's other modules
//   standalone  logo = module icon   items = (empty)
//
// It is drawn only when the app on screen resolves to at least one visible entry
// (Sidebar.workspace_dock_enabled) and the page on screen allows it (page_allows_dock; the desktop
// or apps screen does not). An app that resolves to no entries gets no rail rather than an empty
// stripe: the user button moves back to the body sidebar and the sidebar header carries a switcher
// instead.
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
		// Right-edge handle, mirroring the body sidebar's own collapse handle. While the sidebar is
		// collapsed and only the rail shows, clicking the rail's right edge reopens it. CSS shows it
		// only in the collapsed state (body.sidebar-collapsed), so it does not compete with the
		// sidebar handle while expanded.
		let $resize = $(`<div class="workspace-dock-resize-handle" aria-hidden="true"></div>`);
		$resize.on("click", () => this.sidebar.open());
		this.$dock.append($resize);

		// A visible control for the same action, mirroring the sidebar's own .sidebar-toggle-btn:
		// the same circular button on the rail's right edge, with the chevron pointing right since
		// it only expands. Like the handle, CSS keeps it to the collapsed state.
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

	// Icon shortcuts pinned directly under the app logo: search and notifications, replacing the
	// page header's buttons. They are declared as configuration so the set, the order and each
	// item's tooltip live in one place, and render_shortcuts() turns each entry into a rail button.
	// Every item mirrors <RailItem variant="ghost">: transparent until hovered.
	//
	// Item shape:
	//   name      identifier
	//   icon      icon name passed to frappe.utils.icon
	//   label     tooltip text and accessible label
	//   css_class extra classes on the button (external code hooks off these)
	//   condition () => bool, whether to render this shortcut at all
	//   badge     optional extra markup appended inside the button, such as a count dot
	//   on_click  optional click handler
	//   setup     optional ($item) => {} hook run after the button is built
	get_shortcuts() {
		return [
			{
				name: "search",
				icon: "search",
				label: __("Search"),
				// AwesomeBar's delegated click handler in page.js opens the shared search modal
				// from this class, so keep it or search stops working from the dock.
				css_class: "navbar-modal-search-mobile",
				condition: () => frappe.boot.desk_settings.search_bar,
			},
			{
				name: "notifications",
				icon: "bell",
				label: __("Notifications"),
				// The Notifications view keeps the unread count in sync from these classes (see
				// notifications.js) and toggles the same dropdown the sidebar bell does.
				css_class: "sidebar-notification",
				condition: () => frappe.boot.desk_settings.notifications,
				badge: `<span class="notification-count hidden" aria-live="polite"></span>`,
				on_click: () => this.toggle_notifications(),
				setup: ($item) => {
					// Seed the badge from boot; the Notifications view keeps it updated after
					// that.
					this.sync_notification_count(
						$item,
						frappe.boot.notification_unread_count || 0
					);
				},
			},
		];
	}

	// Render the configured shortcuts under the logo, each as an icon button with a hover tooltip.
	// This runs once, from make(), so handlers are not re-bound.
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
			// Icon-only button, so show its label as a hover tooltip.
			$item.tooltip({ boundary: "window", container: "body", trigger: "hover" });

			this.$shortcuts.append($item);
		});
	}

	// The dock shows unread as a small dot rather than a number, so toggle it on whether any
	// exist.
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

	// User avatar pinned to the bottom of the rail, opening the same dropdown as the sidebar's user
	// button. This runs once, from make(), so the menu is not re-bound on every refresh().
	render_user() {
		this.$user.html(frappe.avatar(frappe.session.user, "avatar-medium"));
		this.sidebar.create_user_menu({ parent: this.$user, button: this.$user });
	}

	refresh() {
		// The dock belongs to the app whose body sidebar is on screen.
		this.app = this.sidebar.get_sidebar_app();
		// It is drawn only if it has entries and the page on screen allows it. The desktop or apps
		// screen, and any page that has not rendered yet, do not.
		let enabled = this.sidebar.workspace_dock_enabled() && this.sidebar.page_allows_dock();
		// Drives the CSS that hides the sidebar's own user button while the rail is active, so
		// switching this off returns the user button to the sidebar.
		$("body").toggleClass("workspace-dock-active", enabled);

		if (!enabled) {
			this.$dock.addClass("hidden");
			return;
		}
		this.$dock.removeClass("hidden");

		// One navigation calls this up to three times: once from the router and twice from
		// Sidebar.refresh(), its own call plus the one inside apply_page_visibility. Each call
		// disposes every tooltip and rebuilds every button, so rendering unconditionally did that
		// two or three times for a rail that had not changed.
		//
		// Everything the rail draws goes into this signature, labels and icons as well as the
		// entries, so renaming a module's sidebar still redraws its tooltip. If the signature
		// matches, there is nothing to redraw.
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

	// The rail's top slot: what you are inside, and the way out. It shows the app's icon when the
	// module on screen belongs to an app, and the module's own icon when it does not. Both link to
	// the desktop, so a module you entered always has a way out.
	//
	// There is no fallback to the first installed app's logo, so no rail shows unrelated branding.
	// Every rail now carries an icon of its own, resolved from data it already holds.
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

	// A module belonging to an app shows that app's logo. An app that declares none gets a letter
	// icon, matching the desktop apps screen.
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

	// A module belonging to no app shows its own icon. No new boot payload is needed, because the
	// module sidebar the rail already reads carries both the header icon and the label.
	module_logo() {
		let sidebar = frappe.boot.module_sidebars[this.sidebar.current_module] || {};
		let label = sidebar.label || this.sidebar.current_module || __("Apps");
		return { icon: this.entry_icon(sidebar.header_icon, label), title: label };
	}

	// A dock entry's icon: the authored one, otherwise a letter icon from its label. The top slot
	// and the items below it share this, so a module looks the same wherever the rail shows it and
	// a pinned workspace gets its own icon on the same terms.
	entry_icon(icon, label) {
		return icon
			? frappe.utils.icon(icon, "md")
			: frappe.utils.desktop_icon(label, "gray", "sm");
	}

	// Inside a module no app claims, this renders nothing: collect_dock_entries returns no
	// entries, and an empty items region is better than a rail of one, since an item permanently
	// active with no alternatives is a switcher that cannot switch.
	render_entries(entries = this.sidebar.collect_dock_entries(this.app)) {
		// Dispose tooltips from the previous render before removing their elements.
		this.$items.find('[data-toggle="tooltip"]').tooltip("dispose");
		this.$items.empty();

		entries.forEach((entry) => {
			let $item = this.make_dock_item(entry);
			if ($item) this.$items.append($item);
		});

		// The rail is icon-only, so show each entry's name as a hover tooltip.
		this.$items.find('[data-toggle="tooltip"]').tooltip({
			boundary: "window",
			container: "body",
			trigger: "hover",
		});
	}

	// One rail button, for either kind of entry. A pinned workspace needs no markup of its own,
	// because `dock_entry` resolved its label and icon from the boot payload the same way a
	// module's come from its sidebar, so from here on the two are the same.
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
