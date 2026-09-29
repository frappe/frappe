// The app switcher: the modules of the app that owns the sidebar on screen. Floating (the default)
// it slides in over the sidebar when the pointer hits the window's left edge; pinned it is a column.
frappe.ui.Dock = class Dock {
	// Pixels from the left edge: reveal at the edge, hide once the pointer is past the tray.
	static REVEAL_EDGE = 1;
	static HIDE_BAND = 90;

	constructor(sidebar) {
		this.sidebar = sidebar;
		this.is_open = false;
		this.enabled = false;
		// The user's preference; `is_pinned` is whether it applies on the page on screen.
		this.pinned = frappe.boot.desk_settings?.dock_mode === "Pinned";
		this.is_pinned = false;
		this.opener = null;
		this.tooltips = [];
		this.make();
	}

	make() {
		this.$dock = $(`<div class="dock hidden" id="desk-dock" role="navigation" aria-label="${__(
			"Apps"
		)}">
			<div class="dock-logo">
				<a class="shell-header" href="/desk">
					<div class="header-logo"></div>
					<div class="title-container">
						<div class="header-title"></div>
					</div>
				</a>
			</div>
			<div class="dock-items"></div>
			<div class="dock-user">
				<button class="dock-item dock-user-button" aria-label="${__("User Menu")}">
					${frappe.avatar(frappe.session.user, "avatar-medium")}
				</button>
			</div>
		</div>`);

		let $container = $(".body-sidebar-container");
		if ($container.length) {
			this.$dock.insertBefore($container);
		} else {
			this.$dock.prependTo("body");
		}

		this.$header = this.$dock.find(".dock-logo .shell-header");
		this.$header_logo = this.$header.find(".header-logo");
		this.$header_title = this.$header.find(".header-title");
		this.$items = this.$dock.find(".dock-items");
		this.$header.on("click", () => this.close());

		this.setup_user_menu();
		this.setup_reveal();
		this.setup_shortcut();
		this.apply_open_state();
	}

	set_pinned(pinned) {
		this.pinned = pinned;
		this.apply_pin();
	}

	// A touch screen cannot summon a floating dock, and a page without the sidebar has no other
	// switcher, so the dock is pinned there whatever the preference.
	should_pin() {
		if (!this.enabled) return false;
		if (this.pinned) return true;
		return !!this.sidebar.current_page()?.hide_sidebar && !frappe.ui.Dock.pointer_can_reveal();
	}

	apply_pin() {
		const pinned = this.should_pin();
		if (pinned === this.is_pinned) return;
		// Set first: `close` refuses while pinned.
		this.is_pinned = pinned;
		$("body").toggleClass("dock-pinned", pinned);
		pinned ? this.open() : this.close();
		this.sidebar.sync_panel_inert();
	}

	setup_user_menu() {
		const $user = this.$dock.find(".dock-user");
		// Otherwise the browser's own title tooltip shows on top of ours.
		$user.find("[title]").removeAttr("title");
		this.sidebar.create_user_menu({
			parent: $user,
			button: $user.find(".dock-user-button"),
			side: "right",
			align: "end",
		});
		new frappe.ui.Tooltip($user.find(".dock-user-button")[0], {
			text: frappe.session.user_fullname,
			side: "right",
			delay: 0,
			offset: 10,
			class: "es-tooltip--plain",
		});
	}

	// `any-hover`, not `hover`: a tablet with a trackpad reports touch as its primary input.
	static pointer_can_reveal() {
		return window.matchMedia("(any-hover: hover)").matches;
	}

	// The edge is read off the pointer rather than a hover strip, which would swallow clicks meant
	// for the sidebar rows under it. Not `mouseleave` either: a dock that slides in under a still
	// pointer never gets `mouseenter`, so it would never get the leave.
	setup_reveal() {
		$(document)
			.off(".dock-edge")
			.on("mousemove.dock-edge", (e) => {
				if (!this.enabled || this.is_pinned) return;
				// Cheap exit for the common case: shut, and nowhere near the edge.
				if (!this.is_open && e.clientX > frappe.ui.Dock.REVEAL_EDGE) return;

				const open = this.should_open({
					over_dock: !!$(e.target).closest(".dock").length,
					holds_focus: this.holds_focus(),
					dist_from_edge: e.clientX,
					currently_open: this.is_open,
				});
				open ? this.open() : this.close();
			});

		$(document)
			.off(".dock-reveal")
			// A trackpad tap reports no travel, so a click can arrive without a move before it.
			.on("click.dock-reveal", (e) => {
				if (!this.is_open) return;
				if ($(e.target).closest(".dock").length) return;
				this.close();
			})
			.on("keydown.dock-reveal", (e) => {
				if (e.key === "Escape" && this.is_open) this.close();
			});

		this.$dock.off("focusout.dock-reveal").on("focusout.dock-reveal", (e) => {
			if (!this.is_open || this.$dock[0].contains(e.relatedTarget)) return;
			this.opener = null;
			this.close();
		});
	}

	// `ctrl+/` already toggles the sidebar.
	setup_shortcut() {
		frappe.ui.keys.add_shortcut({
			shortcut: "shift+ctrl+/",
			action: () => this.toggle_from_keyboard(),
			description: __("Open the app dock"),
			condition: () => this.enabled,
		});
	}

	toggle_from_keyboard() {
		if (this.is_open && !this.is_pinned) {
			this.close();
			return;
		}

		this.opener = document.activeElement;
		this.open();
		this.$items.find(".dock-item").first().trigger("focus");
	}

	holds_focus() {
		return this.$dock[0].contains(document.activeElement);
	}

	should_open({ over_dock, holds_focus, dist_from_edge, currently_open }) {
		if (over_dock || holds_focus) return true;
		if (dist_from_edge <= frappe.ui.Dock.REVEAL_EDGE) return true;
		if (dist_from_edge > frappe.ui.Dock.HIDE_BAND) return false;
		return currently_open;
	}

	open() {
		if (!this.enabled || this.is_open) return;
		this.is_open = true;
		this.apply_open_state();
	}

	close() {
		if (!this.is_open || this.is_pinned) return;
		const had_focus = this.holds_focus();
		const opener = this.opener;
		this.opener = null;

		this.is_open = false;
		this.tooltips.forEach((tip) => tip.hide());
		this.apply_open_state();

		// Focus in a dock turning inert would fall to <body>.
		if (had_focus && opener?.isConnected) opener.focus();
	}

	// `inert` keeps Tab out of a dock that is off screen but still in the document.
	apply_open_state() {
		$("body").toggleClass("dock-open", this.is_open);
		this.$dock.attr("aria-hidden", String(!this.is_open));
		this.$dock.prop("inert", !this.is_open);
	}

	refresh() {
		this.app = this.sidebar.get_sidebar_app();
		this.enabled = this.sidebar.dock_enabled() && this.sidebar.page_allows_dock();
		$("body").toggleClass("dock-active", this.enabled);
		this.apply_pin();

		if (!this.enabled) {
			this.$dock.addClass("hidden");
			this.close();
			return;
		}
		this.$dock.removeClass("hidden");

		// One navigation calls this up to three times, so skip the rebuild when nothing drawn changed.
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

	render_logo() {
		const { icon, title } = this.app ? this.app_logo() : this.module_logo();

		this.$header_logo.html(icon);
		this.$header_title.text(title);
		this.$header.attr("aria-label", __("All apps"));
		if (!this.header_tooltip) {
			this.header_tooltip = new frappe.ui.Tooltip(this.$header[0], {
				text: __("All apps"),
				side: "right",
				delay: 0,
				offset: 10,
				class: "es-tooltip--plain",
			});
		}
	}

	app_logo() {
		return frappe.utils.app_logo(this.app);
	}

	module_logo() {
		let sidebar = frappe.boot.module_sidebars[this.sidebar.current_module] || {};
		let label = sidebar.label || this.sidebar.current_module || __("Apps");
		let icon = frappe.get_module_icon(this.sidebar.current_module);
		return { icon: this.entry_icon(icon, label), title: label };
	}

	entry_icon(icon, label) {
		return icon
			? frappe.utils.icon(icon, "md")
			: frappe.utils.desktop_icon(label, "gray", "sm");
	}

	name_tile($el, label) {
		this.tooltips.push(
			new frappe.ui.Tooltip($el[0], {
				text: label,
				side: "right",
				delay: 0,
				offset: 10,
				class: "es-tooltip--plain",
			})
		);
	}

	render_entries(entries = this.sidebar.collect_dock_entries(this.app)) {
		this.tooltips.forEach((tip) => tip.destroy());
		this.tooltips = [];
		this.$items.empty();

		entries.forEach((entry) => {
			let $item = this.make_dock_item(entry);
			if ($item) this.$items.append($item);
		});
	}

	make_dock_item(entry) {
		let label = entry.label;
		if (!label) return null;
		let icon = this.entry_icon(entry.icon, label);

		let is_active = this.sidebar.is_active_entry(entry);
		// By name, since the sprites load after the page and the symbol may not exist yet.
		let is_duotone = !!entry.icon && entry.icon.endsWith("-duotone");
		let $item = $(`<button
			class="dock-item ${is_active ? "active" : ""} ${is_duotone ? "dock-item--duotone" : ""}"
			aria-label="${frappe.utils.escape_html(label)}"
			${is_active ? 'aria-current="page"' : ""}
		>
			<span class="dock-item-icon">${icon}</span>
			<span class="dock-item-label">${frappe.utils.escape_html(label)}</span>
		</button>`);

		this.name_tile($item, label);

		$item.on("click", () => {
			this.close();
			this.sidebar.open_dock_entry(entry);
		});
		return $item;
	}
};
