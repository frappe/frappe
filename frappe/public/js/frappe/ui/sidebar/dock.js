// Dock: the app switcher, kept off screen until it is called for. It lists the modules of the app
// that owns the sidebar on screen, with that app's mark in the top slot, and it slides in over the
// body sidebar the way the macOS Dock slides in over the desktop.
//
// It is an overlay, not a column. The body sidebar is the desk's permanent navigation and holds
// the left edge of the window; the dock sits one step above it in the hierarchy and one step
// behind it on screen.
//
// It is called up by pushing the pointer into the window's left edge, and the rule for that is
// `should_show` -- ported from the frappe-os desktop's `shouldShowDock`, which had already settled
// the shape of it. Two thresholds rather than one:
//
//   reveal   the pointer has to reach the true edge (REVEAL_EDGE px). Nothing short of that opens
//            it, so travelling past the edge on the way somewhere else leaves it alone, and no
//            timer is needed to tell a deliberate push from a passing one.
//   hide     it closes once the pointer rises clear of HIDE_BAND, about the tray's own reach.
//
// Between the two the answer is whatever it already was. That hysteresis is what makes the tray
// usable: revealing demands the edge, but once out it survives the 50-odd px of travel from the
// edge to the tile you are aiming at, which a single threshold would have closed it on.
//
// The edge is read off the pointer rather than drawn as a strip to hover. A strip would be a real
// element over the leftmost pixels of the sidebar, and those pixels are the left edge of every row
// in it: it would take the clicks aimed at "Item" and "Stock Entry" along with the hovers it
// wanted. Nothing is in front of the sidebar this way, and the sidebar keeps the window's edge.
//
// It is drawn only when the app on screen resolves to at least one visible entry
// (Sidebar.dock_enabled) and the page on screen allows it (page_allows_dock; the desktop or the
// apps screen does not). An app that resolves to no entries gets no dock rather than an empty
// stripe, and its sidebar header carries a switcher menu instead.
//
// Search, notifications, background tasks and the user button are not on the dock. They were while
// the dock was the permanent surface and the sidebar was the thing that came and went; a surface
// that is hidden by default cannot hold them, so all four belong to the sidebar again (see
// Sidebar.add_standard_items and the sidebar's own user button).
frappe.ui.Dock = class Dock {
	// The two thresholds the reveal hangs on, in px from the window's left edge. Neither is a CSS
	// variable, because nothing is drawn at either width: they are distances the pointer is tested
	// against, not boxes.
	//
	// REVEAL_EDGE is the true edge, which is the whole intent test -- a pointer only lands there by
	// being pushed there. HIDE_BAND is roughly the tray's own reach, so the dock stays out across
	// the gap between the edge and the tile being aimed at.
	static REVEAL_EDGE = 1;
	static HIDE_BAND = 90;

	constructor(sidebar) {
		this.sidebar = sidebar;
		this.is_open = false;
		this.enabled = false;
		// Whatever held focus when the keyboard opened the dock, so closing it can hand focus back
		// the way a menu does. Null when the pointer opened it, since the pointer never takes
		// focus away from anything.
		this.opener = null;
		// One per tile, held so they can be torn down when the tiles are replaced.
		this.tooltips = [];
		this.make();
	}

	make() {
		// The body is a horizontal flex row (body-sidebar-container, then main-section). The dock
		// is out of flow, but it is still inserted as the leftmost element so its place in the
		// document matches its place on screen: a screen reader and a Tab reach it before the
		// sidebar it stands in front of.
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
		// The router turns the href into a route without a reload (see router.js), so nothing else
		// takes the dock down on the way out.
		this.$header.on("click", () => this.close());

		this.setup_reveal();
		this.setup_shortcut();
		this.apply_open_state();
	}

	// Whether this device has anything that can hover, and so anything that can push into the
	// window's edge. A touch screen cannot, so on one the dock is drawn and cannot be summoned;
	// the sidebar header keeps its switcher for exactly that case (SidebarHeader.switcher_items).
	//
	// `any-hover` rather than `hover`: a tablet with a trackpad attached reports its primary input
	// as touch, and the trackpad reaches the edge perfectly well.
	static pointer_can_reveal() {
		return window.matchMedia("(any-hover: hover)").matches;
	}

	// -------------------------------------------------------------------------------------------
	// Reveal. Everything that opens the dock and everything that closes it again.
	// -------------------------------------------------------------------------------------------

	setup_reveal() {
		// One listener for both directions. `should_show` is a pure function of where the pointer
		// is and what the dock is already doing, so the loop has nothing to remember and no timer
		// to cancel: every move re-asks the same question and the answer is applied.
		$(document)
			.off(".dock-edge")
			.on("mousemove.dock-edge", (e) => {
				if (!this.enabled) return;
				// Almost every move the desk sees happens with the dock shut and the pointer away
				// from the edge, and for those `should_show` can only answer "stay shut": a shut
				// dock is off screen and inert, so it can be neither under the pointer nor holding
				// focus. Answering here keeps the DOM walk below off all of them.
				if (!this.is_open && e.clientX > frappe.ui.Dock.REVEAL_EDGE) return;

				this.apply_visibility(
					this.should_show({
						over_dock: !!$(e.target).closest(".dock").length,
						holds_focus: this.holds_focus(),
						dist_from_edge: e.clientX,
						currently_shown: this.is_open,
					})
				);
			});

		$(document)
			.off(".dock-reveal")
			// A click anywhere that is not the dock dismisses it, the way a menu goes on the next
			// click elsewhere. The pointer usually gets there first, but a click can outrun a
			// move -- a trackpad tap reports no travel at all.
			.on("click.dock-reveal", (e) => {
				if (!this.is_open) return;
				if ($(e.target).closest(".dock").length) return;
				this.close();
			})
			.on("keydown.dock-reveal", (e) => {
				if (e.key === "Escape" && this.is_open) this.close();
			});

		// Tabbing out of the last tile is leaving the dock, the same as the pointer rising out of
		// the band. Only a move that takes focus somewhere outside counts: focus passing from one
		// tile to the next fires this too.
		this.$dock.off("focusout.dock-reveal").on("focusout.dock-reveal", (e) => {
			if (!this.is_open || this.$dock[0].contains(e.relatedTarget)) return;
			// Focus already went where the user sent it, so `close` must not pull it back.
			this.opener = null;
			this.close();
		});
	}

	// The dock's only entrance used to be the pointer at the window's edge, and a closed dock is
	// `inert`, so Tab never reaches it either. A keyboard had no way in at all, and the header
	// menu drops its switcher wherever there is a dock -- so switching modules was mouse-only.
	//
	// `shift+ctrl+/` because `ctrl+/` already toggles the sidebar, and this is the surface one
	// step above it. The order is how `frappe.ui.keys.get_key` spells a combination, shift before
	// ctrl. Nothing in the browser claims it, and like every desk shortcut it does not fire while
	// typing in a field.
	setup_shortcut() {
		frappe.ui.keys.add_shortcut({
			shortcut: "shift+ctrl+/",
			action: () => this.toggle_from_keyboard(),
			description: __("Open the app dock"),
			condition: () => this.enabled,
		});
	}

	toggle_from_keyboard() {
		if (this.is_open) {
			this.close();
			return;
		}

		this.opener = document.activeElement;
		this.open();
		// `open` lifts `inert`, so the tiles can take focus from here on.
		this.$items.find(".dock-item").first().trigger("focus");
	}

	holds_focus() {
		return this.$dock[0].contains(document.activeElement);
	}

	// Ported from frappe-os `desktop/dock-visibility.ts`. Kept a pure function of its input, and
	// separate from the listener that feeds it, so the branchy part is the part you can read.
	//
	// `over_dock` is ours rather than the port's: the tray happens to sit inside HIDE_BAND today, so
	// the band alone would carry it, but resting on a thing should not depend on that arithmetic
	// holding. The port's other override, for a menu hanging off the dock, is gone with the menu --
	// the mark is a link out to the apps screen now and the tiles are links to modules, so nothing
	// opens over the dock that it has to stay out for.
	//
	// `holds_focus` is ours too. A dock opened from the keyboard has focus in one of its tiles and
	// a pointer that may be anywhere, and a nudge of the mouse must not shut it from under the
	// keyboard that is using it.
	should_show({ over_dock, holds_focus, dist_from_edge, currently_shown }) {
		if (over_dock || holds_focus) return true;
		if (dist_from_edge <= frappe.ui.Dock.REVEAL_EDGE) return true;
		if (dist_from_edge > frappe.ui.Dock.HIDE_BAND) return false;
		return currently_shown;
	}

	apply_visibility(show) {
		show ? this.open() : this.close();
	}

	// Nothing tracks the pointer separately once the dock is out: the one `mousemove.dock-edge`
	// listener above answers both directions, and the hysteresis in `should_show` is what stops it
	// closing the moment the pointer leaves the edge it was summoned from.
	//
	// The obvious alternative -- the dock's own `mouseleave` -- does not work here and is worth
	// recording. The dock slides out from under a pointer that is already resting at the edge and
	// has not moved, and a browser fires no `mouseenter` for an element that arrives beneath a
	// stationary pointer. No enter means no leave, so a dock closed that way stayed out until
	// something else dismissed it.

	open() {
		if (!this.enabled || this.is_open) return;
		this.is_open = true;
		this.apply_open_state();
	}

	close() {
		if (!this.is_open) return;
		// Focus inside a dock about to turn inert would fall to <body>, so it goes back to
		// whatever the keyboard opened the dock from, when that is still on the page.
		const had_focus = this.holds_focus();
		const opener = this.opener;
		this.opener = null;

		this.is_open = false;
		// A bubble is appended to <body>, so nothing about the tray leaving takes it with it.
		this.tooltips.forEach((tip) => tip.hide());
		this.apply_open_state();

		if (had_focus && opener?.isConnected) opener.focus();
	}

	// One class on <body>, the same way the sidebar states its own, so the transform and everything
	// keyed to it live in dock.scss rather than in inline styles here.
	//
	// `inert` rather than `aria-hidden` alone: a dock translated off screen is still in the
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

	refresh() {
		// The dock belongs to the app whose body sidebar is on screen.
		this.app = this.sidebar.get_sidebar_app();
		// It is drawn only if it has entries and the page on screen allows it. The desktop or apps
		// screen, and any page that has not rendered yet, do not.
		this.enabled = this.sidebar.dock_enabled() && this.sidebar.page_allows_dock();
		// `dock-active` says the app on screen has a dock. Nothing about the sidebar depends on it
		// any more -- the dock arrives on top rather than beside -- but the class is what the edge
		// test reads to know whether there is anything to summon, and what other code asks.
		$("body").toggleClass("dock-active", this.enabled);

		if (!this.enabled) {
			this.$dock.addClass("hidden");
			// A dock that has gone must not leave the page holding it open.
			this.close();
			return;
		}
		this.$dock.removeClass("hidden");

		// One navigation calls this up to three times: once from the router and twice from
		// Sidebar.refresh(), its own call plus the one inside apply_page_visibility. Each call
		// rebuilds every button, so rendering unconditionally did that two or three times for a
		// dock that had not changed.
		//
		// Everything the dock draws goes into this signature, labels and icons as well as the
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

	// The dock's top slot: what you are inside, and the way out. It shows the app's icon when the
	// module on screen belongs to an app, and the module's own icon when it does not. Both link to
	// the desktop, so a module you entered always has a way out.
	//
	// There is no fallback to the first installed app's logo, so no dock shows unrelated branding.
	// Every dock now carries an icon of its own, resolved from data it already holds.
	render_logo() {
		const { icon, title } = this.app ? this.app_logo() : this.module_logo();

		// Only the mark and the name change here. The way out to the apps screen is the menu's
		// "All apps" row now, so the header is a menu trigger rather than the link it used to be.
		this.$header_logo.html(icon);
		this.$header_title.text(title);
		// The mark shows which app you are in; what it is for is getting out of it, which is what the
		// name has to say -- a link read out as "ERPNext" gives no clue that pressing it leaves
		// ERPNext. This is the row the header was before a menu moved onto it, and "All apps" is the
		// menu row that held the job in between.
		this.$header.attr("aria-label", __("All apps"));
		// Built once with the header, then renamed in place: the tooltip binds to the node, and the
		// node outlives every module this dock goes on to show.
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

	// A module belonging to an app shows that app's logo. The dock-less sidebar's header draws
	// the same mark, so both read it from frappe.utils.
	app_logo() {
		return frappe.utils.app_logo(this.app);
	}

	// A module belonging to no app shows its own icon. No new boot payload is needed, because the
	// module sidebar the dock already reads carries both the header icon and the label.
	module_logo() {
		let sidebar = frappe.boot.module_sidebars[this.sidebar.current_module] || {};
		let label = sidebar.label || this.sidebar.current_module || __("Apps");
		return { icon: this.entry_icon(sidebar.header_icon, label), title: label };
	}

	// A dock entry's icon: the authored one, otherwise a letter icon from its label. The top slot
	// and the items below it share this, so a module looks the same wherever the dock shows it and
	// a pinned workspace gets its own icon on the same terms.
	entry_icon(icon, label) {
		return icon
			? frappe.utils.icon(icon, "md")
			: frappe.utils.desktop_icon(label, "gray", "sm");
	}

	// Name a tile with the desk's own tooltip, which is what every other icon-only control here
	// uses. Two departures from its defaults, both because of what this tray is:
	//
	//   no arrow   `es-tooltip--plain`. An arrow points a bubble at the one control it belongs to,
	//              which earns its keep in a toolbar of mixed shapes. Here every tile is the same
	//              40px square in one column and every bubble lands in the same place beside it, so
	//              the arrow names nothing the position had not already said.
	//   no delay   the default 500ms is for a label you already half know and are confirming. These
	//              glyphs are the opposite: a stranger cannot guess them, so waiting half a second
	//              per tile to find out is the cost the tooltip exists to remove.
	//
	// Kept so they can be destroyed: the tiles are replaced whenever the module changes, and a
	// bubble showing at that moment would outlive the tile it names.
	name_tile($el, label) {
		this.tooltips.push(
			new frappe.ui.Tooltip($el[0], {
				text: label,
				side: "right",
				delay: 0,
				// The arrow filled the component's default 4px, and there is no arrow here, so the
				// bubble needs a gap of its own. This is the gap it keeps: nothing on the tile
				// moves on hover, so the bubble is not placed against a tile that is about to
				// travel toward it.
				offset: 10,
				class: "es-tooltip--plain",
			})
		);
	}

	// Inside a module no app claims, this renders nothing: collect_dock_entries returns no
	// entries, and an empty items region is better than a dock of one, since an item permanently
	// active with no alternatives is a switcher that cannot switch.
	render_entries(entries = this.sidebar.collect_dock_entries(this.app)) {
		this.tooltips.forEach((tip) => tip.destroy());
		this.tooltips = [];
		this.$items.empty();

		entries.forEach((entry) => {
			let $item = this.make_dock_item(entry);
			if ($item) this.$items.append($item);
		});
	}

	// One dock button, for either kind of entry. A pinned workspace needs no markup of its own,
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

		this.name_tile($item, label);

		$item.on("click", () => {
			// Picking a module is leaving the dock: the sidebar behind it is about to be rebuilt
			// for what was chosen, and that is the thing to look at.
			this.close();
			this.sidebar.open_dock_entry(entry);
		});
		return $item;
	}
};
