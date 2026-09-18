// Dock: the app switcher, kept off screen until it is called for. It lists the modules of the app
// that owns the sidebar on screen, with that app's mark in the top slot, and it slides in over the
// body sidebar the way the macOS Dock slides in over the desktop.
//
// It is an overlay, not a column. The body sidebar is the desk's permanent navigation and holds
// the left edge of the window; the rail sits one step above it in the hierarchy and one step
// behind it on screen.
//
// It is called up by resting the pointer within EDGE_PX of the window's left edge. The rail arms
// only after DWELL_MS, so a pointer merely crossing the edge on its way somewhere else does not
// summon it, and it goes again once the pointer settles anywhere else.
//
// The edge is read off the pointer rather than drawn as a strip to hover. A strip would be a real
// element over the leftmost pixels of the sidebar, and those pixels are the left edge of every row
// in it: it would take the clicks aimed at "Item" and "Stock Entry" along with the hovers it
// wanted. Nothing is in front of the sidebar this way, and the sidebar keeps the window's edge.
//
// It is drawn only when the app on screen resolves to at least one visible entry
// (Sidebar.dock_enabled) and the page on screen allows it (page_allows_dock; the desktop or the
// apps screen does not). An app that resolves to no entries gets no rail rather than an empty
// stripe, and its sidebar header carries a switcher menu instead.
//
// Search, notifications, background tasks and the user button are not on the rail. They were while
// the rail was the permanent surface and the sidebar was the thing that came and went; a surface
// that is hidden by default cannot hold them, so all four belong to the sidebar again (see
// Sidebar.add_standard_items and the sidebar's own user button).
frappe.ui.Dock = class Dock {
	// How long the pointer has to rest against the edge before the rail comes out, and how long it
	// has to stay away before it goes back. Both exist for the same reason: a rail that answered
	// the edge on contact would flash open every time a pointer crossed it, and one that left on
	// contact would drop out from under a pointer travelling the few pixels from the edge to its
	// own first row.
	static DWELL_MS = 250;
	static CLOSE_MS = 220;
	// How close to the window's edge counts as the edge. Not a CSS variable, because nothing is
	// drawn at this width: it is a distance the pointer is tested against, not a box.
	static EDGE_PX = 6;

	constructor(sidebar) {
		this.sidebar = sidebar;
		this.is_open = false;
		this.enabled = false;
		this.make();
	}

	make() {
		// The body is a horizontal flex row (body-sidebar-container, then main-section). The rail
		// is out of flow, but it is still inserted as the leftmost element so its place in the
		// document matches its place on screen: a screen reader and a Tab reach it before the
		// sidebar it stands in front of.
		this.$dock = $(`<div class="dock hidden" id="desk-dock" role="navigation" aria-label="${__(
			"Apps"
		)}">
			<div class="dock-logo">
				<button class="btn-reset shell-header">
					<div class="header-logo"></div>
					<div class="title-container">
						<div class="header-title"></div>
					</div>
					<span class="drop-icon" aria-hidden="true">
						${frappe.utils.icon("chevron-down", "sm", "", "", "", true)}
					</span>
				</button>
			</div>
			<div class="dock-items"></div>
		</div>`);

		let $container = $(".body-sidebar-container");
		if ($container.length) {
			this.$dock.insertBefore($container);
		} else {
			this.$dock.prependTo("body");
		}

		// Built once and never replaced: the header's menu binds to this node, and render_logo
		// rewrites what is inside it rather than the node itself.
		this.$header = this.$dock.find(".dock-logo .shell-header");
		this.$header_logo = this.$header.find(".header-logo");
		this.$header_title = this.$header.find(".header-title");
		this.$items = this.$dock.find(".dock-items");

		this.setup_reveal();
		this.apply_open_state();
	}

	// -------------------------------------------------------------------------------------------
	// Reveal. Everything that opens the rail and everything that closes it again.
	// -------------------------------------------------------------------------------------------

	setup_reveal() {
		$(document)
			.off(".dock-edge")
			// Watching the pointer is the whole trigger. It is one comparison per move and it runs
			// only while a rail exists and is not already out; `arm` is what makes it a dwell
			// rather than a hair trigger, by leaving a timer it started alone rather than
			// restarting it on every pixel.
			.on("mousemove.dock-edge", (e) => {
				if (!this.enabled || this.is_open) return;
				if (e.clientX <= frappe.ui.Dock.EDGE_PX) {
					this.arm();
				} else {
					this.disarm();
				}
			});

		$(document)
			.off(".dock-reveal")
			// A click anywhere that is not the rail dismisses it, the way a menu goes on the next
			// click elsewhere. The pointer usually gets there first, but a click can outrun
			// CLOSE_MS.
			.on("click.dock-reveal", (e) => {
				if (!this.is_open) return;
				if ($(e.target).closest(".dock").length) return;
				this.close();
			})
			.on("keydown.dock-reveal", (e) => {
				if (e.key === "Escape" && this.is_open) this.close();
			});
	}

	// What closes the rail once it is out.
	//
	// Not the rail's own mouseleave, which is the obvious answer and does not work: the rail slides
	// out from under a pointer that is already resting against the edge and has not moved, and a
	// browser does not fire mouseenter for an element that arrives beneath a stationary pointer. No
	// enter means no leave, so the rail stayed out until something else dismissed it.
	//
	// So the pointer is followed instead, and only while the rail is out: a move that lands off the
	// rail starts the close, and one that lands back on it cancels it. The edge counts as on it, or
	// the rail would begin closing in the gap between the window's edge and its own first pixel.
	// The listener is bound on open and dropped on close, so nothing is watching the document the
	// rest of the time.
	track_pointer(on) {
		$(document).off("mousemove.dock-track");
		if (!on) return;
		$(document).on("mousemove.dock-track", (e) => {
			const on_rail =
				$(e.target).closest(".dock").length || e.clientX <= frappe.ui.Dock.EDGE_PX;
			on_rail ? this.hold() : this.release();
		});
	}

	// Start the dwell, or leave a running one alone. Restarting it on every move would mean a
	// pointer held at the edge kept resetting its own countdown and the rail never came out.
	arm() {
		if (this.dwell_timer) return;
		this.dwell_timer = setTimeout(() => {
			this.dwell_timer = null;
			this.open();
		}, frappe.ui.Dock.DWELL_MS);
	}

	disarm() {
		clearTimeout(this.dwell_timer);
		this.dwell_timer = null;
	}

	hold() {
		clearTimeout(this.close_timer);
	}

	release() {
		clearTimeout(this.close_timer);
		this.close_timer = setTimeout(() => this.close(), frappe.ui.Dock.CLOSE_MS);
	}

	open() {
		if (!this.enabled) return;
		this.disarm();
		this.hold();
		if (this.is_open) return;
		this.is_open = true;
		this.track_pointer(true);
		this.apply_open_state();
	}

	close() {
		this.disarm();
		clearTimeout(this.close_timer);
		if (!this.is_open) return;
		this.is_open = false;
		this.track_pointer(false);
		this.apply_open_state();
	}

	// One class on <body>, the same way the sidebar states its own, so the transform and everything
	// keyed to it live in dock.scss rather than in inline styles here.
	//
	// `inert` rather than `aria-hidden` alone: a rail translated off screen is still in the
	// document and still focusable, so a Tab from the sidebar would otherwise land in rows nobody
	// can see. Both are set, since `inert` is what takes it out of the tab order and
	// `aria-hidden` is what older assistive technology reads.
	apply_open_state() {
		$("body").toggleClass("dock-open", this.is_open);
		this.$dock.attr("aria-hidden", String(!this.is_open));
		this.$dock.prop("inert", !this.is_open);
	}

	// -------------------------------------------------------------------------------------------
	// Contents
	// -------------------------------------------------------------------------------------------

	// The menu that names this app's own affairs -- Edit Sidebar, the navbar settings, help, and
	// the way out to the apps screen -- hangs on the rail's header. SidebarHeader owns which header
	// carries a second copy of the same menu on its own header, and only ever one of the two is in
	// front of you, since the rail covers the panel rather than standing beside it.
	//
	// Done from refresh() rather than make() because the rail can be built before the header it
	// borrows the menu from. The node is built once, so this is too: the dropdown binds to the
	// element and reads its rows fresh on every open.
	setup_header_menu() {
		if (this.header_menu || !this.sidebar.sidebar_header) return;
		this.header_menu = this.sidebar.sidebar_header.attach_menu(this.$header);
	}

	refresh() {
		this.setup_header_menu();
		// The dock belongs to the app whose body sidebar is on screen.
		this.app = this.sidebar.get_sidebar_app();
		// It is drawn only if it has entries and the page on screen allows it. The desktop or apps
		// screen, and any page that has not rendered yet, do not.
		this.enabled = this.sidebar.dock_enabled() && this.sidebar.page_allows_dock();
		// `dock-active` says the app on screen has a rail. Nothing about the sidebar depends on it
		// any more -- the rail arrives on top rather than beside -- but the class is what the edge
		// test reads to know whether there is anything to summon, and what other code asks.
		$("body").toggleClass("dock-active", this.enabled);

		if (!this.enabled) {
			this.$dock.addClass("hidden");
			// A rail that has gone must not leave the page holding it open.
			this.close();
			return;
		}
		this.$dock.removeClass("hidden");

		// One navigation calls this up to three times: once from the router and twice from
		// Sidebar.refresh(), its own call plus the one inside apply_page_visibility. Each call
		// rebuilds every button, so rendering unconditionally did that two or three times for a
		// rail that had not changed.
		//
		// Everything the rail draws goes into this signature, labels and icons as well as the
		// entries, so renaming a module's sidebar still redraws its row. If the signature matches,
		// there is nothing to redraw.
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

		// Only the mark and the name change here. The way out to the apps screen is the menu's
		// "All apps" row now, so the header is a menu trigger rather than the link it used to be.
		this.$header_logo.html(icon);
		this.$header_title.text(title);
		this.$header.attr("aria-label", title);
	}

	// A module belonging to an app shows that app's logo. The dock-less sidebar's header draws
	// the same mark, so both read it from frappe.utils.
	app_logo() {
		return frappe.utils.app_logo(this.app);
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
		this.$items.empty();

		entries.forEach((entry) => {
			let $item = this.make_dock_item(entry);
			if ($item) this.$items.append($item);
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
			class="dock-item ${is_active ? "active" : ""}"
			aria-label="${frappe.utils.escape_html(label)}"
			${is_active ? 'aria-current="page"' : ""}
		>
			<span class="dock-item-icon">${icon}</span>
			<span class="dock-item-label">${frappe.utils.escape_html(label)}</span>
		</button>`);

		$item.on("click", () => {
			// Picking a module is leaving the rail: the sidebar behind it is about to be rebuilt
			// for what was chosen, and that is the thing to look at.
			this.close();
			this.sidebar.open_dock_entry(entry);
		});
		return $item;
	}
};
