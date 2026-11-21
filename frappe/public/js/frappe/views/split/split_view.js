/**
 * frappe.views.SplitView
 *
 * The list on the left and the selected record on the right, for working through records one
 * after another. A DocType opts in with "Allow Split View". The open record is the route's last
 * part, `/desk/<doctype>/view/split/<name>`, and picking another one keeps the list as it is.
 *
 * Every setting is optional, in `frappe.listview_settings[doctype].split_view`:
 *
 *   fields: ["job_title"]          extra fields to fetch for the rows
 *   get_item(doc, row_data) {}     returns { title, subtitle, meta, badge, avatar }, any of them,
 *                                  to replace that part of the row (see frappe.ui.List);
 *                                  row_data is what get_row_data returned for the row, if anything
 *   get_row_data(docs) {}          for values the list query cannot fetch (counts, titles from
 *                                  other records); gets the loaded rows after each refresh and
 *                                  returns a promise of { [name]: object }. The rows are drawn
 *                                  first and drawn again, in place, when it resolves.
 *   render_detail({ name, $wrapper, view }) {}
 *                                  draws the record into $wrapper, which is dropped when the
 *                                  selection changes; may return { refresh(), destroy() }. After
 *                                  changing the record, call view.refresh_item(name), or
 *                                  view.refresh() when other rows changed too. Without it,
 *                                  frappe.views.SplitViewPreview (split_preview.js) shows it.
 *
 * A custom detail can also call view.select_next(offset), which loads the next page when it steps
 * past the last loaded row, and view.get_position(name), e.g. for "3 of 14".
 *
 * The two columns, their scrolling, the keys that step through the rows and the next page loading
 * by itself come from frappe.ui.SplitPane. Below 1024px the list and the detail take turns on the
 * full width. Styles are in desk/split_view.scss.
 */
frappe.provide("frappe.views");

frappe.views.SplitView = class SplitView extends frappe.views.ListView {
	get view_name() {
		return "Split";
	}

	get show_saved_layout_menu() {
		return false;
	}

	setup_defaults() {
		return super.setup_defaults().then(() => {
			this.view = "Split";
			this.page_name = frappe.views.get_split_page_name(frappe.get_route());
			this.split_settings = this.settings.split_view || {};
			this.selected_name = null;
			this.has_pushed_detail = false;
			this.row_data = {};
			this.row_data_request = 0;
		});
	}

	// picking a record routes back to this same page, which keeps the list and swaps the detail
	show() {
		if (!this.init_promise || !this.is_same_list_as_last_route()) {
			return super.show().then(() => this.show_selected(this.get_route_name(), true));
		}
		if (this.has_new_route_filters()) {
			return this.before_refresh()
				.then(() => this.refresh())
				.then(() => this.show_selected(this.get_route_name()));
		}
		frappe.route_options = null;
		this.update_url_with_filters();
		this.show_selected(this.get_route_name());
		return Promise.resolve();
	}

	/** Whether the route brings filters other than the ones applied; none keeps the applied ones. */
	has_new_route_filters() {
		const incoming = frappe.route_options || {};
		if ($.isEmptyObject(incoming)) return false;
		const current = Object.fromEntries(this.get_search_params());
		const keys = new Set([...Object.keys(current), ...Object.keys(incoming)]);
		return [...keys].some((key) => cstr(current[key]) !== cstr(incoming[key]));
	}

	get_route_name() {
		const route = frappe.get_route();
		return route.length > 3 ? route.slice(3).join("/") : null;
	}

	is_same_list_as_last_route() {
		const last_route = frappe.route_history.slice(-2)[0];
		return (
			Boolean(last_route) && frappe.views.get_split_page_name(last_route) === this.page_name
		);
	}

	is_current_route() {
		return frappe.views.get_split_page_name(frappe.get_route()) === this.page_name;
	}

	async set_fields() {
		await super.set_fields();
		for (const field of this.split_settings.fields || []) {
			this._add_field(field);
		}
	}

	setup_paging_area() {
		this.$paging_area = $("<div></div>");
	}

	async setup_view() {
		await this.setup_columns();
		this.setup_split_layout();
		this.setup_events();
		this.settings.onload && this.settings.onload(this);
		this.show_restricted_list_indicator_if_applicable();
	}

	setup_split_layout() {
		this.pane = new frappe.ui.SplitPane({
			empty: { title: __("Nothing to show") },
			on_select: (name, event) => this.on_select(name, event),
			has_more: () => this.has_more(),
			load_more: () => this.load_more(),
			page: this.page,
			fold_sidebar: true,
			keys: {
				condition: (event) => !this.is_key_taken(event) && this.data.length > 0,
			},
		});
		this.$split = this.pane.$el.appendTo(this.$frappe_list);
		this.$frappe_list.addClass("has-split-view");
		this.$detail = this.pane.$detail;
		this.list = this.pane.list;
		this.detail_loader = new frappe.ui.DetailLoader({
			fetch: (name, { silent }) =>
				frappe.xcall(
					"frappe.desk.doc_preview.get_preview",
					{ doctype: this.doctype, name },
					"GET",
					{ silent }
				),
			get_neighbours: (name) => this.pane.get_neighbour_ids(name),
		});
		this.$no_result.hide();
		this.$result.append(this.list.$el).appendTo(this.pane.$rows);
		this.render_detail();
	}

	on_select(name, event) {
		// List sends Enter on a row as a keydown
		if (event?.type === "keydown" && name === this.selected_name) return this.open_form(name);
		// Enter acts on the focused row, so focus follows a step
		const focus_row = !event && $(document.activeElement).closest(".es-list__row").length;
		this.select(name);
		if (focus_row) {
			this.list.$el
				.find(".es-list__row[data-selected]")
				.get(0)
				?.focus({ preventScroll: true });
		}
	}

	setup_events() {
		this.setup_realtime_updates();
		this.setup_new_doc_event();
		this.setup_keyboard_navigation();
	}

	is_dialog_open() {
		return $(".modal:visible").length > 0;
	}

	is_key_taken(e) {
		return e.isDefaultPrevented() || this.is_dialog_open();
	}

	setup_keyboard_navigation() {
		const is_control_focused = () =>
			$(document.activeElement).is("a, button, [role=button], [role=radio]");
		const shortcuts = [
			[
				"enter",
				(e) => {
					if (this.is_key_taken(e) || is_control_focused() || !this.selected_name) {
						return false;
					}
					this.open_form(this.selected_name);
				},
				__("Open selected record"),
			],
			[
				"escape",
				() => {
					if (this.is_dialog_open() || !this.selected_name) return false;
					this.select(null);
				},
				__("Close selected record"),
			],
		];
		for (const [shortcut, action, description] of shortcuts) {
			frappe.ui.keys.add_shortcut({ shortcut, action, description, page: this.page });
		}
	}

	load_more() {
		this.start = this.data.length;
		this.page_length = this.selected_page_count;
		return this.refresh_now();
	}

	prepare_data(r) {
		const rows = Array.isArray(r.message) ? r.message : r.message?.values || [];
		// read from the reply, as rows dropped from this.data since must not end the loading
		this.is_last_page_full = rows.length >= this.page_length;
		if (this.start === 0) this.is_count_loading = true;
		super.prepare_data(r);
	}

	has_more() {
		return Boolean(this.is_last_page_full);
	}

	/**
	 * Where a row is among all the records that match the filters: { index (1-based), total,
	 * is_estimate }. `is_estimate` means there are at least `total`, as more rows can load and the
	 * count is off, capped or still loading.
	 */
	get_position(name = this.selected_name) {
		const index = this.data.findIndex((doc) => doc.name === name) + 1;
		const loaded = this.data.length;
		if (!this.has_more()) return { index, total: loaded, is_estimate: false };
		const count = this.is_count_loading ? null : this.total_count;
		if (count == null || count === this.count_upper_bound) {
			return { index, total: Math.max(loaded, cint(count) - 1), is_estimate: true };
		}
		return { index, total: Math.max(loaded, count), is_estimate: count < loaded };
	}

	/** Steps the selection; past the last loaded row it brings in the next page first. */
	select_next(offset) {
		return this.pane.step(offset);
	}

	/** Open a record in the detail pane (null clears it) and put it in the URL. */
	select(name, { replace = false } = {}) {
		name = name || null;
		if (name === this.selected_name) return;
		// Picks replace the history entry, so Back leaves the page. Below 1024px the detail covers
		// the list, so opening one from the list adds an entry and Back shows the list again.
		if (!name && this.has_pushed_detail) return window.history.back();
		const is_covering_list = !this.pane.is_wide && !this.selected_name && !replace;
		this.show_selected(name);
		if (is_covering_list) this.has_pushed_detail = true;

		frappe.route_options = Object.fromEntries(this.get_search_params());
		if (!is_covering_list) frappe.route_flags.replace_route = true;
		frappe.set_route(["List", this.doctype, "Split", ...(name ? [name] : [])]);
	}

	show_selected(name, force = false) {
		if (name === this.selected_name && !force) return;
		const was_open = Boolean(this.selected_name);
		this.selected_name = name;
		if (!name) this.has_pushed_detail = false;
		this.pane.set_selected(name, { scroll: true });
		this.$split.toggleClass("has-selection", Boolean(name));
		this.render_detail();

		// below 1024px the detail takes the list's place in the shared scroller
		if (!this.pane.is_wide && this.is_current_route()) {
			const scroller = document.querySelector(".main-section");
			if (name && !was_open) this.list_scroll_top = scroller?.scrollTop;
			if (scroller) scroller.scrollTop = name ? 0 : this.list_scroll_top || 0;
		}
	}

	open_form(name) {
		frappe.set_route("Form", this.doctype, name);
	}

	set_result_height() {
		this.pane?.fit_height();
	}

	toggle_result_area() {
		this.$no_result.hide();
		this.toggle_actions_menu_button(false);
	}

	render() {
		this.pane.set_items(this.data.map((doc) => this.get_item(doc)));
		this.load_row_data(this.data, true);
		this.detail?.update_position?.();
	}

	/** Asks get_row_data for the rows' extra values and redraws the rows it answered for. */
	load_row_data(docs, is_refresh = false) {
		const get_row_data = this.split_settings.get_row_data;
		if (!get_row_data || !docs.length) return Promise.resolve();
		// a refresh supersedes the one before it; a single row's answer never goes stale
		const request = is_refresh ? ++this.row_data_request : this.row_data_request;
		return Promise.resolve(get_row_data(docs)).then((row_data) => {
			if (!row_data || request !== this.row_data_request) return;
			Object.assign(this.row_data, row_data);
			for (const doc of docs) {
				if (!(doc.name in row_data)) continue;
				const current = this.data.find((d) => d.name === doc.name);
				if (current) this.list.update_item(doc.name, this.get_item(current));
			}
		});
	}

	render_list() {
		this.render();
	}

	render_header() {}

	render_skeleton() {}

	sync_right_width() {}

	apply_styles_basedon_dropdown() {}

	get_count_element() {
		return $();
	}

	render_count() {
		const request = (this.count_request = (this.count_request || 0) + 1);
		this.is_count_loading = true;
		const counted = this.list_view_settings?.disable_count
			? Promise.resolve()
			: this.get_count_str();
		counted.then(() => {
			if (request !== this.count_request) return;
			this.is_count_loading = false;
			this.update_empty_detail();
			this.detail?.update_position?.();
		});
	}

	remove_list_items(names) {
		for (const name of names) {
			this.list.remove_item(name);
			this.detail_loader.forget(name);
		}
		this.render_count();
		if (!names.includes(this.selected_name)) return;

		// a record that left the filters stays open; a deleted one is closed
		const name = this.selected_name;
		frappe.db.exists(this.doctype, name).then((exists) => {
			if (exists || this.selected_name !== name) return;
			if (this.is_current_route()) this.select(null, { replace: true });
			else this.show_selected(null);
		});
	}

	process_document_refreshes() {
		const names = this.pending_document_refreshes.map((d) => d.name);
		for (const name of names) this.detail_loader.forget(name);
		super.process_document_refreshes();
		if (names.includes(this.selected_name)) this.detail?.refresh?.();
	}

	/**
	 * Fetch one row again and re-render it, or drop it when it no longer matches the filters.
	 * For detail panels that change the record they show.
	 */
	refresh_item(name) {
		this.detail_loader.forget(name);
		const call_args = this.get_call_args();
		call_args.args.filters.push([this.doctype, "name", "=", name]);
		call_args.args.start = 0;

		return frappe.call(call_args).then(({ message }) => {
			const doc = message ? frappe.utils.dict(message.keys, message.values)[0] : null;
			const index = this.data.findIndex((d) => d.name === name);
			if (!doc) {
				if (index === -1) return;
				this.data.splice(index, 1);
				this.list.remove_item(name);
			} else if (index === -1) {
				return;
			} else {
				this.data[index] = doc;
				this.list.update_item(name, this.get_item(doc));
				this.load_row_data([doc]);
			}
			this.render_count();
		});
	}

	get_item(doc) {
		const title = this.get_title(doc);
		const indicator = this.get_indicator(doc);
		const item = {
			id: doc.name,
			title,
			subtitle: this.get_item_subtitle(doc, [title, indicator?.label]),
			meta: this.get_relative_time(doc.modified),
			// every row would say the same, e.g. "Open" when filtered by status Open
			badge: this.is_pinned_by_filters(indicator) ? undefined : indicator,
			avatar: this.meta.image_field
				? { label: title, image: doc[this.meta.image_field] || undefined }
				: undefined,
		};
		const custom = this.split_settings.get_item?.(doc, this.row_data[doc.name]);
		return { ...item, ...custom, id: doc.name };
	}

	/** "1w", "3d", "now". */
	get_relative_time(datetime) {
		return cstr(frappe.datetime.prettyDate(datetime, true)).replace(/(\d)\s+/, "$1");
	}

	/** Whether the filters already say what the indicator would. */
	is_pinned_by_filters(indicator) {
		if (!indicator?.filter) return false;
		const [fieldname, operator, ...value] = indicator.filter.split(",");
		return this.get_filters_for_args().some(
			(filter) =>
				filter[1] === fieldname &&
				filter[2] === operator &&
				cstr(filter[3]) === value.join(",")
		);
	}

	get_title(doc) {
		const title = this.meta.title_field && doc[this.meta.title_field];
		return this.get_plain_text(title) || cstr(doc.name);
	}

	get_indicator(doc) {
		const indicator = frappe.get_indicator(doc, this.doctype);
		if (!indicator) return undefined;
		return {
			label: cstr(indicator[0]),
			theme: indicator[1] === "black" ? "gray" : indicator[1],
			// the filter that shows only this indicator, e.g. "status,=,Open"
			filter: typeof indicator[2] === "string" ? indicator[2] : undefined,
		};
	}

	// Up to two list-view values, leaving out the ones the title and the badge already show.
	get_item_subtitle(doc, shown) {
		const values = [];
		for (const df of this.get_fields_in_list_view()) {
			if (!df.in_list_view || df.fieldname === this.meta.title_field) continue;
			this.add_link_title(df, doc);
			const value = this.get_plain_text(this.format_value(df, doc));
			if (!value || shown.includes(value) || values.includes(value)) continue;
			values.push(value);
			if (values.length === 2) break;
		}
		return values.join(" · ");
	}

	// The row carries a link's title; the formatter reads it from the cache, which may not have it yet.
	add_link_title(df, doc) {
		const title_field = this.link_field_title_fields?.[df.fieldname];
		const title = title_field && doc[`${df.fieldname}_${title_field}`];
		if (title) frappe.utils.add_link_title(df.options, doc[df.fieldname], title);
	}

	format_value(df, doc) {
		return frappe.format(doc[df.fieldname], df, { no_icon: true, only_value: true }, doc);
	}

	get_plain_text(html) {
		return frappe.utils.html2text(cstr(html)).replace(/\s+/g, " ").trim();
	}

	destroy_detail() {
		this.detail?.destroy?.();
		this.detail = null;
		this.$detail.empty();
	}

	render_detail() {
		this.destroy_detail();
		const name = this.selected_name;
		if (!name) {
			this.render_empty_detail();
			return;
		}

		const render_detail = this.split_settings.render_detail;
		if (!render_detail) {
			this.detail = new frappe.views.SplitViewPreview({
				view: this,
				name,
				$parent: this.$detail,
			});
			return;
		}
		this.make_back_button().addClass("split-view-back").appendTo(this.$detail);
		const $wrapper = $('<div class="split-view-custom-detail"></div>').appendTo(this.$detail);
		this.detail = render_detail({ name, $wrapper, view: this }) || null;
	}

	make_back_button() {
		return frappe.ui.button({
			icon: "arrow-left",
			variant: "ghost",
			tooltip: __("Back to list"),
			css_class: "split-view-back-button",
			onclick: () => this.select(null),
		});
	}

	render_empty_detail() {
		frappe.ui
			.empty_state({
				icon: "columns-2",
				title: __("No {0} selected", [__(this.doctype)]),
				description: this.get_empty_description(),
				css_class: "split-view-empty",
			})
			.appendTo(this.$detail);
	}

	// the count arrives after the rows, so the empty state is drawn again with it
	update_empty_detail() {
		if (this.selected_name) return;
		this.destroy_detail();
		this.render_empty_detail();
	}

	get_empty_description() {
		const count = this.total_count;
		if (count == null) return "";
		if (!count) return __("No records match the filters.");
		if (count === 1) return __("1 record matches the filters.");
		const label =
			count === this.count_upper_bound
				? `${format_number(count - 1, null, 0)}+`
				: format_number(count, null, 0);
		return __("{0} records match the filters.", [label]);
	}
};
