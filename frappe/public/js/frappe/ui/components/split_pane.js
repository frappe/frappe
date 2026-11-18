frappe.provide("frappe.ui");

// below this the owner decides what the narrow screen shows (see split_view.scss)
const WIDE_QUERY = "(min-width: 1024px)";
// the panes keeping the sidebar folded; it unfolds once none does
const sidebar_holders = new Set();

/**
 * @typedef {Object} SplitPaneOpts
 * @property {Node|JQuery|Array<Node|JQuery>} [header] Above both columns, e.g. tabs.
 * @property {Node|JQuery|Array<Node|JQuery>} [list_header] At the top of the list column, e.g. a search box.
 * @property {Node|JQuery} [detail] The detail column's content; it fills the column and scrolls itself.
 * @property {EmptyStateOpts} [empty] Shown in the list column when there are no items.
 * @property {(id:string, event?:Event)=>void} [on_select] A row was clicked or activated (with its event), or `step` moved (without). The owner selects it with `set_selected`.
 * @property {()=>boolean} [has_more] Whether more rows can load.
 * @property {()=>Promise} [load_more] Loads the next page and hands it over with `set_items`.
 * @property {frappe.ui.Page} [page] The page that holds the pane; the pane re-fits its height when the page shows again.
 * @property {boolean} [fold_sidebar] Folds the desk sidebar to its rail while `page` shows the pane on a wide screen; leaving the page brings it back.
 * @property {{condition?:(event:Event, shortcut:string)=>boolean, next_label?:string, previous_label?:string}} [keys] Binds j/k and down/up on `page` to `step`.
 */

/**
 * The two-pane shell of a master-detail page: a list column of 384px beside a detail column from
 * 1024px, each scrolling on its own, filling the screen under what sits above the pane. The next
 * page loads by itself as the list's end scrolls near. Below 1024px the columns stack and the page
 * scrolls; the owner decides what shows there. The owner keeps the selection and the routing.
 * Styles are in desk/split_view.scss. Not in the desk bundle: load it first with
 * `await frappe.require("split_view.bundle.js")`.
 *
 * @example
 * const pane = new frappe.ui.SplitPane({
 *   list_header: $search,
 *   detail: panel.$el,
 *   on_select: (id) => { pane.set_selected(id); panel.load(id); },
 *   has_more: () => rows.length < total,
 *   load_more: () => fetch_next().then(() => pane.set_items(items)),
 *   page,
 *   fold_sidebar: true,
 *   keys: {},
 * });
 * page.main.append(pane.$el);
 * pane.set_items(items);
 * pane.fit_height();
 */
frappe.ui.SplitPane = class SplitPane {
	/** @param {SplitPaneOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		this.selected = null;
		this.is_loading = false;
		this.media = window.matchMedia(WIDE_QUERY);
		this.make();
		this.bind_events();
		this.bind_keys();
		this.sync_sidebar();
	}

	bind_events() {
		this.handle_resize = () => this.$el.is(":visible") && this.fit_height();
		this.handle_media_change = () => {
			this.sync_sidebar();
			// the list scrolls in its column only on a wide screen
			if (!this.$placeholder) this.watch_list_end();
		};
		// a resize while the page was away left the height as it was
		this.handle_page_show = () => {
			this.handle_resize();
			this.sync_sidebar();
		};
		this.handle_page_hide = () => this.sync_sidebar();
		window.addEventListener("resize", this.handle_resize);
		this.media.addEventListener("change", this.handle_media_change);
		$(this.opts.page?.wrapper)
			.on("show", this.handle_page_show)
			.on("hide", this.handle_page_hide);
	}

	make() {
		const opts = this.opts;
		this.$el = $(`<div class="split-view">
			<div class="split-view-list"><div class="split-view-rows"></div></div>
			<div class="split-view-detail"></div>
		</div>`);
		this.$list = this.$el.find(".split-view-list");
		this.$rows = this.$el.find(".split-view-rows");
		this.$detail = this.$el.find(".split-view-detail").append(opts.detail || []);
		if (opts.header) {
			this.$header = $(`<div class="split-view-header"></div>`).append(opts.header);
			this.$el.prepend(this.$header);
		}
		if (opts.list_header) {
			this.$list_header = $(`<div class="split-view-list-header"></div>`).append(
				opts.list_header
			);
			this.$list.prepend(this.$list_header);
		}
		this.list = new frappe.ui.List({
			variant: "flat",
			items: [],
			empty: opts.empty,
			on_click: (item, list, event) => opts.on_select?.(item.id, event),
		});
		this.$rows.append(this.list.$el);
		this.$list_end = $(`<div class="split-view-list-end" aria-hidden="true"></div>`);
	}

	/** Replace the rows, and the groups when given; brings the rows back after `set_placeholder`. */
	set_items(items, groups) {
		this.$placeholder?.remove();
		this.$placeholder = null;
		this.list.$el.show();
		this.list.set_items(items, groups);
		this.list.set_selected(this.selected);
		this.watch_list_end();
	}

	/** Shows `element` in place of the rows, e.g. while they load or when nothing matches. */
	set_placeholder(element) {
		this.more_observer?.disconnect();
		this.$list_end.detach();
		this.$placeholder?.remove();
		this.$placeholder = $(element).prependTo(this.$rows);
		this.list.$el.hide();
	}

	/** Highlight a row; pass null to clear. Pass `scroll: true` to bring it into view. */
	set_selected(id, { scroll = false } = {}) {
		this.selected = id ?? null;
		this.list.set_selected(this.selected, { scroll });
	}

	/** Moves the selection by `delta` rows, loading the next page first when it steps past the loaded rows. */
	async step(delta) {
		let ids = this.get_row_ids();
		const index = ids.indexOf(this.selected);
		if (index !== -1 && index + delta >= ids.length && this.opts.has_more?.()) {
			if (this.is_loading) return;
			await this.load_next_page();
			ids = this.get_row_ids();
		}
		if (!ids.length) return;
		const next = index === -1 ? 0 : Math.min(Math.max(index + delta, 0), ids.length - 1);
		if (ids[next] !== this.selected) this.opts.on_select?.(ids[next]);
	}

	/** Row ids in the order they show, groups included. */
	get_row_ids() {
		return [...this.list.rows.keys()];
	}

	/** The ids of the rows below and above `id`, for frappe.ui.DetailLoader to load early. */
	get_neighbour_ids(id) {
		const ids = this.get_row_ids();
		const index = ids.indexOf(id);
		return index === -1 ? [] : [ids[index + 1], ids[index - 1]];
	}

	async load_next_page() {
		if (this.is_loading || !this.opts.has_more?.()) return;
		this.is_loading = true;
		try {
			await this.opts.load_more();
		} finally {
			this.is_loading = false;
		}
	}

	/** The next page loads by itself once the end of the list scrolls near. */
	watch_list_end() {
		this.more_observer?.disconnect();
		if (!this.opts.has_more?.()) return this.$list_end.detach();
		this.$list_end.appendTo(this.$rows);
		this.more_observer = new IntersectionObserver(
			(entries) => entries[0].isIntersecting && this.load_next_page(),
			// on a narrow screen the page scrolls, not the column
			{ root: this.is_wide ? this.$rows[0] : null, rootMargin: "400px 0px" }
		);
		this.more_observer.observe(this.$list_end[0]);
	}

	/** On a wide screen, gives the pane the height left under its top, so the page does not scroll. */
	fit_height() {
		const pane = this.$el[0];
		const scroller = pane.closest(".main-section");
		if (!this.is_wide || !scroller) return pane.style.removeProperty("height");
		// measured with the height still set, so the columns keep their scroll
		const scroller_rect = scroller.getBoundingClientRect();
		const top = pane.getBoundingClientRect().top - scroller_rect.top + scroller.scrollTop;
		pane.style.height = Math.floor(scroller_rect.height - top) + "px";
	}

	/**
	 * While its page shows on a wide screen, the pane keeps the sidebar folded to its rail without
	 * saving that as the viewer's choice; the sidebar comes back once no pane keeps it folded.
	 */
	sync_sidebar() {
		const { page, fold_sidebar } = this.opts;
		const is_shown =
			fold_sidebar && page && !this.is_destroyed && $(page.wrapper).is(":visible");
		const sidebar = frappe.app?.sidebar;
		if (is_shown && this.is_wide) {
			sidebar_holders.add(this);
			sidebar?.fold_for_page();
		} else if (sidebar_holders.delete(this) && !sidebar_holders.size) {
			sidebar?.unfold_after_leaving_page();
		}
	}

	get is_wide() {
		return this.media.matches;
	}

	bind_keys() {
		const page = this.opts.page;
		if (!this.opts.keys || !page) return;
		const { condition, next_label, previous_label } = this.opts.keys;
		const next = next_label || __("Select next record");
		const previous = previous_label || __("Select previous record");
		this.shortcuts = [
			["j", 1, next],
			["down", 1, next],
			["k", -1, previous],
			["up", -1, previous],
		];
		for (const [shortcut, delta, description] of this.shortcuts) {
			frappe.ui.keys.add_shortcut({
				shortcut,
				description,
				page,
				action: (event) => {
					if (condition && !condition(event, shortcut)) return false;
					this.step(delta);
				},
			});
		}
	}

	/** Takes the pane out; what came in as header, list_header and detail is detached, not destroyed. */
	destroy() {
		this.is_destroyed = true;
		window.removeEventListener("resize", this.handle_resize);
		this.media.removeEventListener("change", this.handle_media_change);
		$(this.opts.page?.wrapper)
			.off("show", this.handle_page_show)
			.off("hide", this.handle_page_hide);
		this.release_sidebar();
		this.more_observer?.disconnect();
		for (const [shortcut] of this.shortcuts || []) {
			frappe.ui.keys.off(shortcut, this.opts.page);
		}
		this.$header?.children().detach();
		this.$list_header?.children().detach();
		this.$detail.children().detach();
		this.$el.remove();
	}

	// a pane that takes this one's place in the same task keeps the sidebar folded, so it does not
	// unfold and fold again in between
	release_sidebar() {
		if (!sidebar_holders.delete(this)) return;
		queueMicrotask(() => {
			if (!sidebar_holders.size) frappe.app?.sidebar?.unfold_after_leaving_page();
		});
	}
};
