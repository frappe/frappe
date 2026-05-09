frappe.provide("frappe.search");

/** First N Global Search Settings rows used as implicit default pins. Toolbar shows every pinned DocType. */
frappe.search.GLOBAL_SEARCH_VISIBLE_DT_LIMIT = 5;
frappe.search.GLOBAL_SEARCH_PIN_STORAGE_KEY = "global-search-pinned-doctypes";

/** “All” summary: per-doctype “Show more” at or above this count when browsing all DocTypes. */
frappe.search.GLOBAL_SEARCH_SUMMARY_SHOW_MORE_MIN = 5;
/** Extra field values beyond this show as “and n more”. */
frappe.search.GLOBAL_SEARCH_FIELD_INLINE_PREVIEW_LIMIT = 3;

frappe.search.SearchDialog = class {
	constructor(opts) {
		$.extend(this, opts);
		this.make();
	}

	make() {
		this.search_dialog = new frappe.ui.Dialog({
			minimizable: true,
			size: "extra-large",
			on_page_show: () => this.focus_global_search_input(),
		});
		this.set_header();
		this.$wrapper = $(this.search_dialog.$wrapper).addClass("search-dialog");
		this.$body = $(this.search_dialog.body);
		this.$input = this.$wrapper.find(".search-input");
		this.setup();
	}

	/** Header `.search-input` is outside `Dialog.fields_list`; base `focus_on_first_input` skips it. */
	focus_global_search_input() {
		const input = this.$input?.get?.(0);
		if (!input) return;
		input.focus({ preventScroll: true });
		if ((input.value || "").length) input.select();
	}

	set_header() {
		this.search_dialog.header
			.addClass("search-header")
			.find(".title-section")
			.html(
				`<div class="input-group text-muted">
					<input type="text" class="form-control search-input">
				</div>
				<span class="search-icon">
					${frappe.utils.icon("search")}
				</span>`
			);
		const $actions = this.search_dialog.$wrapper.find(".modal-actions");
		$actions.find(".btn-open-global-search-settings").remove();
		const $gs = this.make_global_search_settings_btn();
		if ($gs) {
			$actions.prepend($gs);
		}
	}

	make_global_search_settings_btn() {
		if (!frappe.model.can_read("Global Search Settings")) return null;
		const label = __("Configure search settings");
		return $(
			`<button type="button" class="btn btn-ghost icon-btn btn-open-global-search-settings">`
		)
			.attr({
				title: label,
				"aria-label": label,
			})
			.append(frappe.utils.icon("settings", "sm"))
			.on("click", (e) => {
				e.preventDefault();
				e.stopPropagation();
				this.search_dialog.hide();
				frappe.set_route("Form", "Global Search Settings", "Global Search Settings");
			});
	}

	setup() {
		this.modal_state = 0;
		this.current_keyword = "";
		this.more_count = 20;
		this.full_lists = {};
		this.nav_lists = {};
		this.global_doctype_filter = "";
		this._global_search_settings_promise = null;
		this.init_search_objects();
		this.bind_input();
		this.bind_events();
	}

	init_search_objects() {
		this.searches = {
			global_search: {
				input_placeholder: __("Search"),
				empty_state_text: __("Search for anything"),
				no_results_status: () => __("No Results found"),
				get_results: (keywords, callback) => {
					frappe.search.utils
						.get_global_results(keywords, 0, null, this.global_doctype_filter || "")
						.then(
							(global_results) => callback(global_results, keywords),
							(err) => console.error(err)
						);
				},
			},
			tags: {
				input_placeholder: __("Search"),
				empty_state_text: __("Search for anything"),
				no_results_status: (keyword) =>
					"<div>" + __("No documents found tagged with {0}", [keyword]) + "</div>",
				get_results: (keywords, callback) => {
					frappe.tags.utils.get_tag_results(keywords).then(
						(global_results) => callback(global_results, keywords),
						(err) => {
							console.error(err);
						}
					);
				},
			},
		};
	}

	update($r) {
		this.$wrapper.find(".loading-state").addClass("hide");
		this.$body.append($r);
		if (this.$body.find(".search-results").length > 1) {
			this.$body.find(".search-results").first().addClass("hide");
			$r.removeClass("hide");
			this.$body.find(".search-results").first().remove();
		} else {
			$r.removeClass("hide");
		}
	}

	put_placeholder(status_text) {
		let $shell = $(frappe.render_template("search")).addClass("hide");
		const tipLine =
			__("Use ampersand to match multiple terms") + " (" + __("e.g.") + " Marie&John)";
		const show_ampersand_empty_tip =
			status_text === __("Search for anything") &&
			this.search === this.searches["global_search"];
		const ampersandBlock = show_ampersand_empty_tip
			? `<div class="global-search-empty-state-tip text-muted">${frappe.utils.escape_html(
					tipLine
			  )}</div>`
			: "";
		$shell.find(".results-area").html(
			`<div class="empty-state">
				<div class="text-center">
					<img src="/assets/frappe/images/ui-states/search-empty-state.svg"
						alt="Generic Empty State"
						class="null-state"
					>
					<div class="empty-state-text">${frappe.utils.escape_html(status_text)}</div>
					${ampersandBlock}
				</div>
			</div>`
		);
		this.update($shell);
		this.sync_global_search_filter_bar();
	}

	bind_input() {
		const wait_ms = 300;
		this._debounced_search_input = frappe.utils.debounce(() => {
			if (this.$input.val() === this.current_keyword) return;
			const keywords = this.$input.val();
			if (keywords.length > 1) {
				this.get_results(keywords);
			} else {
				this.current_keyword = "";
				this.global_doctype_filter = "";
				this.put_placeholder(this.search.empty_state_text);
			}
		}, wait_ms);
		this.$input.on("input", () => this._debounced_search_input());
		this.$wrapper.on("hide.bs.modal.globalSearch", () => {
			this._debounced_search_input?.cancel?.();
		});
	}

	bind_events() {
		// Sidebar
		this.$body.on("click", ".list-link", (e) => {
			const $link = $(e.currentTarget);
			this.$body.find(".search-sidebar").find(".list-link").removeClass("active selected");
			$link.addClass("active selected");
			const type = $link.attr("data-category");
			this.$body.find(".results-area").empty().html(this.full_lists[type]);
			this.$body.find(".module-section-link").first().focus();
		});

		// Summary more links
		this.$body.on("click", ".section-more", (e) => {
			e.preventDefault();
			const type = $(e.currentTarget).attr("data-category");
			if ($(e.currentTarget).attr("data-fetch-type") === "Global") {
				this.apply_global_doctype_filter(type || "");
				return;
			}
			this.$body.find(".search-sidebar").find(`*[data-category="${type}"]`).trigger("click");
		});

		this.$body.on("click", ".global-search-filter-pill", (e) => {
			e.stopPropagation();
			this.apply_global_doctype_filter($(e.currentTarget).attr("data-doctype") || "");
		});

		this.$wrapper.on("click", (e) => {
			if (!$(e.target).closest(".global-search-more-dropdown-wrap").length)
				this.close_global_search_more_menus();
		});

		this.$body.on("click", ".global-search-more-trigger", (e) => {
			e.preventDefault();
			e.stopPropagation();
			const $dd = $(e.currentTarget).siblings(".global-search-more-dropdown");
			const opening = !$dd.hasClass("menu-open");
			this.close_global_search_more_menus();
			if (opening) $dd.addClass("menu-open");
		});

		this.$body.on("click", ".global-search-more-dropdown", (e) => e.stopPropagation());

		this.$body.on("click", ".global-search-dd-pick-doctype", (e) => {
			e.preventDefault();
			e.stopPropagation();
			this.close_global_search_more_menus();
			this.apply_global_doctype_filter($(e.currentTarget).attr("data-doctype") || "");
		});

		this.$body.on("click", ".global-search-pin-btn", (e) => {
			e.preventDefault();
			e.stopPropagation();
			const $btn = $(e.currentTarget);
			const dt = $btn.attr("data-doctype");
			const action = $btn.attr("data-pin-action") || "";
			if (!dt) return;
			if (action === "remove") this.remove_global_search_pin(dt);
			else if (action === "add") this.add_global_search_pin(dt);
			this.sync_global_search_filter_bar();
		});

		// Back-links (mobile-view)
		this.$body.on("click", ".all-results-link", () => {
			this.$body
				.find(".search-sidebar")
				.find('*[data-category="All Results"]')
				.trigger("click");
		});

		// Full list “More” buttons
		this.$body.on("click", ".list-more", (e) => {
			e.preventDefault();
			const $trigger = $(e.currentTarget);
			const type = $trigger.attr("data-category");
			const fetch_type = $trigger.attr("data-search");
			const $panel = $trigger.closest(".global-search-table-panel");
			const $list = $panel.find(".global-search-results-list").first();
			var current_count = $list.length
				? Math.max(0, $list.children(".list-row-container").length - 1)
				: this.$body.find(".result").length;
			if (fetch_type === "Global") {
				frappe.search.utils
					.get_global_results(
						this.current_keyword,
						current_count,
						this.more_count,
						this.global_doctype_filter || type
					)
					.then(
						(doctype_results) => {
							doctype_results.length &&
								this.add_more_global_table_rows(
									type,
									doctype_results,
									$trigger,
									$list
								);
						},
						(err) => {
							console.error(err);
						}
					);
			} else {
				let results = this.nav_lists[type].slice(0, this.more_count);
				this.nav_lists[type].splice(0, this.more_count);
				this.add_more_results([{ title: type, results: results }]);
			}
		});

		// Switch to global search link
		this.$body.on("click", ".switch-to-global-search", () => {
			this.search = this.searches["global_search"];
			this.$input.attr("placeholder", this.search.input_placeholder);
			this.put_placeholder(this.search.empty_state_text);
			this.get_results(this.current_keyword);
		});
	}

	init_search(keywords, search_type) {
		this.global_doctype_filter = "";
		this.search = this.searches[search_type];
		this.$input.attr("placeholder", this.search.input_placeholder);
		this.put_placeholder(this.search.empty_state_text);
		this.get_results(keywords);
		this.search_dialog.show();
		this.$input.val(keywords);
	}

	/** Keyboard shortcut: open full Global Search panel (not the Awesome Bar). */
	open_global_search_dialog(keywords) {
		keywords = (keywords || "").trim();
		this.global_doctype_filter = "";
		this.search = this.searches["global_search"];
		this.$input.attr("placeholder", this.search.input_placeholder);
		this.search_dialog.show();
		this.$input.val(keywords);
		if (keywords.length > 1) {
			this.get_results(keywords);
		} else {
			this.current_keyword = keywords;
			this.put_placeholder(this.search.empty_state_text);
		}
	}

	get_results(keywords) {
		this.current_keyword = keywords;
		if (this.$body.find(".empty-state").length > 0) {
			this.put_placeholder(__("Searching ..."));
		} else {
			this.$wrapper.find(".loading-state").removeClass("hide");
		}

		if (this.current_keyword.charAt(0) === "#") {
			this.global_doctype_filter = "";
			this.search = this.searches["tags"];
		} else {
			this.search = this.searches["global_search"];
		}

		this.search.get_results(keywords, this.parse_results.bind(this));
	}

	parse_results(result_sets, keyword) {
		result_sets = result_sets.filter(function (set) {
			return set.results.length > 0;
		});
		if (result_sets.length > 0) {
			this.render_data(result_sets);
		} else {
			this.put_placeholder(this.search.no_results_status(keyword));
		}
	}

	render_data(result_sets) {
		let $search_results = $(frappe.render_template("search")).addClass("hide");
		let $sidebar = $search_results.find(".search-sidebar").empty();
		let sidebar_item_html =
			'<li class="search-sidebar-item standard-sidebar-item list-link" data-category="{0}">' +
			'<a><span class="ellipsis">{1}</span></a></li>';

		this.modal_state = 0;
		this.full_lists = {
			"All Results": $('<div class="results-summary"></div>'),
		};
		this.nav_lists = {};

		let global_nonempty = [];
		let nav_nonempty = [];
		result_sets.forEach((set) => {
			if (set.results.length === 0) return;
			if (set.fetch_type === "Global") {
				global_nonempty.push(set);
			} else {
				nav_nonempty.push(set);
			}
		});

		const prepend_all = global_nonempty.length >= 1 || nav_nonempty.length > 1;

		if (prepend_all) {
			$sidebar.prepend($(__(sidebar_item_html, ["All Results", __("All Results")])));
		}

		nav_nonempty.forEach((set) => {
			$sidebar.append($(__(sidebar_item_html, [set.title, __(set.title)])));
			this.add_section_to_summary(set.title, set.results, set.fetch_type);
			this.full_lists[set.title] = this.render_full_list(
				set.title,
				set.results,
				set.fetch_type
			);
		});

		global_nonempty.forEach((set) => {
			this.add_section_to_summary(set.title, set.results, set.fetch_type);
			this.full_lists[set.title] = this.render_full_list(
				set.title,
				set.results,
				set.fetch_type
			);
		});

		const show_global_filters = this.search !== this.searches["tags"];

		const finish_draw = () => {
			this.update($search_results);
			const $pill_host = $(this.search_dialog.body).find(".global-search-doctype-filters");
			this.toggle_global_search_filters($pill_host, show_global_filters);
			if (show_global_filters) {
				this.render_doctype_filter_bar_into($pill_host);
			}
			$(this.search_dialog.body).find(".list-link").first().trigger("click");
		};

		if (show_global_filters) {
			this.ensure_global_search_allowed_doctypes().then(() => finish_draw());
		} else {
			finish_draw();
		}
	}

	sync_global_search_filter_bar() {
		if (this.search === this.searches["tags"]) {
			const $pill_host = this.$body.find(".global-search-doctype-filters");
			this.toggle_global_search_filters($pill_host, false);
			return;
		}
		const redraw = () => {
			const $pill_host = this.$body.find(".global-search-doctype-filters");
			this.toggle_global_search_filters($pill_host, true);
			this.render_doctype_filter_bar_into($pill_host);
		};
		/** Promise `.then` runs on a microtask — pin/unpin would update one frame late. */
		if (this._cached_global_search_allowed !== undefined) {
			redraw();
			return;
		}
		this.ensure_global_search_allowed_doctypes().then(redraw);
	}

	toggle_global_search_filters($host, visible) {
		if (visible) {
			$host.removeClass("hide");
		} else {
			$host.empty().addClass("hide");
		}
	}

	apply_global_doctype_filter(dt) {
		this.global_doctype_filter = dt || "";
		this.get_results(this.current_keyword);
	}

	close_global_search_more_menus() {
		this.$wrapper.find(".global-search-more-dropdown").removeClass("menu-open");
	}

	_global_search_allowed_set() {
		const allow = Object.create(null);
		for (const d of this._cached_global_search_allowed || []) if (d) allow[d] = 1;
		return allow;
	}

	ensure_global_search_allowed_doctypes() {
		if (!this._global_search_settings_promise) {
			this._global_search_settings_promise = new Promise((resolve) => {
				frappe.call({
					method: "frappe.client.get",
					args: {
						doctype: "Global Search Settings",
						name: "Global Search Settings",
					},
					callback: (res) => {
						if (!res.exc && res.message && res.message.allowed_in_global_search) {
							const rows = (res.message.allowed_in_global_search || []).slice();
							rows.sort(
								(a, b) => (parseInt(a.idx, 10) || 0) - (parseInt(b.idx, 10) || 0)
							);
							this._cached_global_search_allowed = rows
								.map((row) => row.document_type)
								.filter(Boolean);
						} else {
							this._cached_global_search_allowed = [];
						}
						resolve(this._cached_global_search_allowed);
					},
					error: () => {
						this._cached_global_search_allowed = [];
						resolve([]);
					},
				});
			});
		}
		return this._global_search_settings_promise;
	}

	/**
	 * explicit=false: missing key — baseline pins from first N settings rows.
	 * explicit=true: user JSON (including []) is authoritative.
	 */
	read_global_search_pin_state() {
		const key = frappe.search.GLOBAL_SEARCH_PIN_STORAGE_KEY;
		let raw = null;
		try {
			raw = localStorage.getItem(key);
		} catch (_) {
			raw = null;
		}
		if (raw === null) {
			try {
				const u = frappe.session && frappe.session.user ? frappe.session.user : "guest";
				const legacy_key = "frappe_global_search_pins::" + encodeURIComponent(u);
				const legacy_val = localStorage.getItem(legacy_key);
				if (legacy_val !== null) {
					localStorage.setItem(key, legacy_val);
					localStorage.removeItem(legacy_key);
					raw = legacy_val;
				}
			} catch (_) {
				/* ignore */
			}
		}
		if (raw === null) return { explicit: false, pins: [] };
		try {
			let arr = JSON.parse(raw);
			if (!Array.isArray(arr)) return { explicit: true, pins: [] };
			return { explicit: true, pins: arr.filter((d) => !!d) };
		} catch {
			return { explicit: true, pins: [] };
		}
	}

	write_global_search_pins(pins) {
		const uniq = [];
		const seen = {};
		(pins || []).forEach(function (dt) {
			if (!dt || seen[dt]) return;
			seen[dt] = 1;
			uniq.push(dt);
		});
		try {
			localStorage.setItem(
				frappe.search.GLOBAL_SEARCH_PIN_STORAGE_KEY,
				JSON.stringify(uniq)
			);
		} catch (e) {
			/* quota or private mode */
		}
	}

	/** First N doctypes from Global Search Settings (same order as backend). */
	default_pinned_doctypes_from_settings() {
		const allowed = this._cached_global_search_allowed || [];
		const lim = frappe.search.GLOBAL_SEARCH_VISIBLE_DT_LIMIT;
		return allowed.slice(0, Math.min(lim, allowed.length));
	}

	current_effective_pins_list() {
		const allow = this._global_search_allowed_set();
		const st = this.read_global_search_pin_state();
		const base = !st.explicit ? this.default_pinned_doctypes_from_settings() : st.pins;
		return base.filter((d) => allow[d]);
	}

	add_global_search_pin(dt) {
		const allow = this._global_search_allowed_set();
		if (!dt || !allow[dt]) return;

		const st = this.read_global_search_pin_state();
		let next = !st.explicit
			? this.default_pinned_doctypes_from_settings().filter((d) => allow[d])
			: st.pins.filter((d) => allow[d]).slice();
		if (next.indexOf(dt) === -1) next.push(dt);
		this.write_global_search_pins(next);
	}

	remove_global_search_pin(dt) {
		const allow = this._global_search_allowed_set();
		const st = this.read_global_search_pin_state();
		const next = !st.explicit
			? this.default_pinned_doctypes_from_settings().filter((d) => allow[d] && d !== dt)
			: st.pins.filter((d) => allow[d] && d !== dt);
		this.write_global_search_pins(next);
	}

	build_global_search_more_menu_dom(pinned_ordered, unpinned_ordered) {
		const pin_icon = frappe.utils.icon("pin", "xs");
		const unpin_icon = frappe.utils.icon("pin-off", "xs");
		let html = "";
		const row = (dt, label, action) => {
			const esc = frappe.utils.escape_html(dt || "");
			const safe_label = frappe.utils.escape_html(label || dt || "");
			let pin_btn = "";
			if (action === "unpin") {
				pin_btn = `<button type="button" class="btn btn-xs btn-default global-search-pin-btn" data-pin-action="remove" data-doctype="${esc}" title="${__(
					"Unpin"
				)}" aria-label="${__("Unpin")}">${unpin_icon}</button>`;
			} else if (action === "pin") {
				pin_btn = `<button type="button" class="btn btn-xs btn-default global-search-pin-btn" data-pin-action="add" data-doctype="${esc}" title="${__(
					"Pin"
				)}" aria-label="${__("Pin")}">${pin_icon}</button>`;
			}
			return `<div class="global-search-more-row">
				<button type="button" class="btn btn-xs btn-link global-search-dd-pick-doctype ellipsis" data-doctype="${esc}">${safe_label}</button>
				<div class="global-search-pin-cell">${pin_btn}</div>
			</div>`;
		};

		html += `<div class="global-search-more-group"><div class="global-search-more-group-title">${__(
			"Pinned"
		)}</div>`;
		if (pinned_ordered.length) {
			pinned_ordered.forEach((dt) => {
				html += row(dt, __(dt), "unpin");
			});
		} else {
			html += `<div class="global-search-more-empty text-muted">${__(
				"No pinned document types."
			)}</div>`;
		}
		html += `</div><div class="global-search-more-group"><div class="global-search-more-group-title">${__(
			"Other"
		)}</div>`;
		if (unpinned_ordered.length) {
			unpinned_ordered.forEach((dt) => {
				html += row(dt, __(dt), "pin");
			});
		} else {
			html += `<div class="global-search-more-empty text-muted">${__(
				"No other document types."
			)}</div>`;
		}
		html += "</div>";
		return html;
	}

	render_doctype_filter_bar_into($host) {
		const keep_more_dropdown_open =
			$host.find(".global-search-more-dropdown.menu-open").length > 0;

		const dt_allowed = this._cached_global_search_allowed || [];
		let pinned_matching = this.current_effective_pins_list();
		let unpinned_ordered = dt_allowed.filter((dt) => !pinned_matching.includes(dt));
		/** One chip per pinned DocType (strip wraps); not capped here. */
		let visible_doctypes = pinned_matching.slice();
		let active_dt = this.global_doctype_filter || "";
		/** Selected DocType must appear in the toolbar if it is not among the visible chips. */
		let show_overflow_chip =
			!!active_dt &&
			dt_allowed.indexOf(active_dt) !== -1 &&
			visible_doctypes.indexOf(active_dt) === -1;

		let $toolbar = $('<div class="global-search-filter-toolbar">');
		let $strip = $('<div class="global-search-visible-pills">');

		let add_pill = (lbl, dt, extra_cls = "") =>
			$("<button>")
				.attr({ type: "button", "data-doctype": dt || "", title: lbl })
				.addClass(
					"btn btn-xs btn-default global-search-filter-pill ellipsis" +
						(extra_cls ? " " + extra_cls : "")
				)
				.text(lbl)
				.toggleClass("active", (active_dt || "") === (dt || ""));

		$strip.append(add_pill(__("All"), ""));
		visible_doctypes.forEach((dt) => {
			$strip.append(add_pill(__(dt), dt, ""));
		});

		if (show_overflow_chip) {
			$strip.append(
				add_pill(__(active_dt), active_dt, "global-search-filter-overflow-pick")
			);
		}

		let $more_wrap = $('<div class="global-search-more-dropdown-wrap">');
		let $more_btn = $(
			'<button type="button" class="btn btn-xs btn-default global-search-more-trigger">'
		)
			.append(frappe.utils.icon("menu", "xs"))
			.append($('<span class="global-search-more-label">').text(" " + __("More")));
		let $dropdown = $('<div class="global-search-more-dropdown shadow rounded">').html(
			this.build_global_search_more_menu_dom(pinned_matching, unpinned_ordered)
		);

		if (pinned_matching.length + unpinned_ordered.length > 0) {
			$more_wrap.append($more_btn).append($dropdown);
			$strip.append($more_wrap);
			if (keep_more_dropdown_open) {
				$dropdown.addClass("menu-open");
			}
		}

		$toolbar.append($strip);

		let $toolbar_row = $('<div class="global-search-toolbar-row">');
		$toolbar_row.append($toolbar);
		$host.empty().append($toolbar_row);
	}

	build_global_search_table_panel(doctype, results_slice, keywords, options = {}) {
		const cols = frappe.search.utils.global_search_field_columns_for_results(results_slice);
		const max_rows = options.max_rows == null ? results_slice.length : options.max_rows;
		let $panel = $('<div class="global-search-table-panel">');
		let $list = $("<div>")
			.addClass("list-item-table global-search-results-list mb-0")
			.attr("data-doctype", doctype || "");

		const nameLabel = __("Name");
		const name_head = frappe.utils.escape_html(nameLabel);
		let header_cols_html = `
			<div class="list-row-col ellipsis list-subject level global-search-grid-col global-search-list-head-subject">
				<span class="level-item" title="${name_head}">${nameLabel}</span>
			</div>`;
		for (let c = 0; c < cols.length; c++) {
			const ch = frappe.utils.escape_html(cols[c]);
			header_cols_html += `<div class="list-row-col ellipsis global-search-grid-col"><span title="${ch}">${ch}</span></div>`;
		}
		$list.append(
			`<div class="list-row-container global-search-list-header">
				<header class="level list-row-head text-muted">
					<div class="level-left list-header-subject global-search-level-left-multi">
						${header_cols_html}
					</div>
				</header>
			</div>`
		);

		results_slice
			.slice(0, max_rows)
			.forEach((r) => this.append_global_result_list_row(r, cols, keywords, doctype, $list));
		$panel.append($list);
		return $panel;
	}

	append_global_result_list_row(result, columns, keywords, type, $list) {
		const utils = frappe.search.utils;
		const fields = utils.parse_global_search_fields(result._global_raw_content || "");
		let avatar_html = "";
		if (result.image) {
			avatar_html = frappe.get_avatar("avatar-small", result.label, result.image);
		}
		let route_url = "#";
		if (result.route) {
			route_url = frappe.router.make_url(result.route);
		}
		const $name_link = $('<a class="global-search-name-link ellipsis">')
			.attr("href", route_url)
			.html(utils.highlight_global_search_terms(result.label, keywords));

		$name_link.attr("title", result.label);
		$name_link.on("click", (e) => {
			e.preventDefault();
			e.stopPropagation();
			if (result.route_options) {
				frappe.route_options = result.route_options;
			}
			var previous_hash = window.location.hash;
			frappe.set_route(result.route);
			if (window.location.hash === previous_hash) {
				frappe.router.route();
			}
		});

		let $name_inner = $('<div class="global-search-name-cell-inner">');
		if (avatar_html) {
			$name_inner.append($(avatar_html));
		}
		$name_inner.append($name_link);

		let $subject = $(
			'<div class="list-row-col ellipsis list-subject level global-search-grid-col">'
		);
		$subject.attr("title", result.label);
		$subject.append($('<span class="level-item">').append($name_inner));

		const field_value_parts = (raw) => {
			if (raw == null) return [""];
			if (Array.isArray(raw)) return raw.map((p) => String(p));
			return [String(raw)];
		};

		let $level_left = $('<div class="level-left global-search-level-left-multi">').append(
			$subject
		);
		const row_title_bits = [result.label];
		const previewLim = frappe.search.GLOBAL_SEARCH_FIELD_INLINE_PREVIEW_LIMIT;
		for (let i = 0; i < columns.length; i++) {
			const parts = field_value_parts(fields[columns[i]]);
			const total = parts.length;
			const plain_full = parts.join("\n");
			row_title_bits.push(plain_full);

			let innerHtml = "";
			if (total > previewLim) {
				const head = parts.slice(0, previewLim);
				const moreN = total - previewLim;
				const moreLbl = __("and {0} more", [String(moreN)]);
				const tailHint = ` <span class="global-search-field-more-hint">${frappe.utils.escape_html(
					moreLbl
				)}</span>`;
				const linesBeforeLast = head.slice(0, -1);
				const lastPreview = head[previewLim - 1];
				const lastLineHtml =
					utils.highlight_global_search_terms(lastPreview, keywords) + tailHint;
				innerHtml =
					linesBeforeLast.length > 0
						? linesBeforeLast
								.map((p) => utils.highlight_global_search_terms(p, keywords))
								.join("<br>") +
						  "<br>" +
						  lastLineHtml
						: lastLineHtml;
			} else {
				innerHtml = parts
					.map((p) => utils.highlight_global_search_terms(p, keywords))
					.join("<br>");
			}

			const multiline = total > 1 || total > previewLim || plain_full.indexOf("\n") !== -1;
			let $field_col = $(
				'<div class="list-row-col global-search-field-col global-search-grid-col">'
			);
			if (multiline) {
				$field_col.addClass("global-search-field-col--multiline");
			} else {
				$field_col.addClass("ellipsis");
			}
			$field_col.html(innerHtml).attr("title", plain_full);
			$level_left.append($field_col);
		}

		let $row = $('<div class="level list-row">').append($level_left);
		let $container = $('<div class="list-row-container">')
			.attr("title", row_title_bits.filter(Boolean).join("\n"))
			.append($row);
		$list.append($container);
	}

	render_full_list(type, results, fetch_type) {
		let max_length = fetch_type === "Global" ? 100 : 20;

		let $results_list = $(`<div class="results-summary">
			<div class="result-section full-list ${type}-section col-sm-12">
				<div class="result-title"> ${__(type)}</div>
				<div class="result-body">
				</div>
			</div>
		</div>`);

		if (fetch_type === "Global") {
			const $panel = this.build_global_search_table_panel(
				type,
				results,
				this.current_keyword,
				{
					max_rows: max_length,
				}
			);
			$results_list.find(".result-body").append($panel);
			if (results.length > max_length) {
				const cat_esc = frappe.utils.escape_html(type || "");
				$(`<button type="button" class="btn btn-default btn-xs mt-2 list-more" data-search="Global" data-category="${cat_esc}">
					${__("More")}
				</button>`).appendTo($panel);
			}
		} else {
			results.slice(0, max_length).forEach((result) => {
				$results_list.find(".result-body").append(this.render_result(type, result));
			});
		}

		if (results.length > 0) {
			if (fetch_type === "Nav") this.nav_lists[type] = results;

			if (fetch_type !== "Global" && results.length > max_length) {
				const cat_esc = frappe.utils.escape_html(type || "");
				$(`<button type="button" class="btn btn-default btn-xs mt-2 list-more" data-search="${fetch_type}"
					data-category="${cat_esc}" data-count="${max_length}">
						${__("More")}
				</button>`).appendTo($results_list.find(".result-body"));
			}
		}
		return $results_list;
	}

	add_section_to_summary(type, results, fetch_type) {
		if (fetch_type === "Global") {
			const results_word = results.length === 1 ? __("result") : __("results");
			let title_row = __(type) + " (" + results.length + " " + results_word + ")";
			let $result_section =
				$(`<div class="col-sm-12 result-section global-summary" data-type="${type || ""}">
				<div class="result-title">${title_row}</div>
				<div class="result-body">
				</div>
			</div>`).appendTo(this.full_lists["All Results"]);

			const $panel = this.build_global_search_table_panel(
				type,
				results,
				this.current_keyword,
				{}
			);
			$result_section.find(".result-body").append($panel);

			const min_show = frappe.search.GLOBAL_SEARCH_SUMMARY_SHOW_MORE_MIN;
			if (!this.global_doctype_filter && results.length >= min_show) {
				const dt_esc = frappe.utils.escape_html(type || "");
				const $btn = $("<button>", {
					type: "button",
					class: "btn btn-default btn-xs section-more mt-2",
				})
					.attr("data-fetch-type", "Global")
					.attr("data-category", dt_esc)
					.text(__("Show more"));
				const $wrap = $('<div class="global-search-summary-show-more">').append($btn);
				$result_section.find(".result-body").append($wrap);
			}
			return;
		}

		let section_length = 4;
		let more_html = "";
		let get_result_html = (result) => this.render_result(type, result);

		if (results.length > section_length) {
			const cat_esc = frappe.utils.escape_html(type || "");
			more_html = `<div>
				<button type="button" class="btn btn-default btn-xs section-more mt-2" data-fetch-type="Nav" data-category="${cat_esc}">${__(
				"More"
			)}</button>
			</div>`;
		}

		let $result_section = $(`<div class="col-sm-12 result-section" data-type="${type || ""}">
			<div class="result-title">${__(type)}</div>
			<div class="result-body">
				${more_html}
			</div>
		</div>`).appendTo(this.full_lists["All Results"]);

		$result_section
			.find(".result-body")
			.prepend(results.slice(0, section_length).map(get_result_html));
	}

	get_link(result) {
		let link = "";
		if (result.route) {
			link = `href="${frappe.router.make_url(result.route)}"`;
		} else if (result.data_path) {
			link = `data-path=${result.data_path}"`;
		}
		return link;
	}

	render_result(type, result) {
		let image_html = "";
		if (result.image !== undefined) {
			let avatar_html = frappe.get_avatar("avatar-medium", result.label, result.image);
			image_html = `<a ${this.get_link(result)}>
				<div class="result-image">
					${avatar_html}
				</div>
			</a>`;
		}

		let link_html = `<a ${this.get_link(result)} class="result-section-link">${
			result.label
		}</a>`;
		let title_html = !result.description
			? link_html
			: `<b>${link_html}</b><div class="description"> ${result.description} </div>`;

		let result_text = `<div class="result-text">
			${title_html}
		</div>`;

		let $result = $(`<div class="result ${type}-result">
			${image_html}
			${result_text}
			${result.subtypes || ""}
		</div>`);

		if (!result.description) {
			this.handle_result_click(result, $result);
		}

		return $result;
	}

	handle_result_click(result, $result) {
		if (result.route_options) {
			frappe.route_options = result.route_options;
		}
		$result.on("click", () => {
			// this.toggle_minimize();
			if (result.onclick) {
				result.onclick(result.match);
			} else {
				var previous_hash = window.location.hash;
				frappe.set_route(result.route);
				// hashchange didn't fire!
				if (window.location.hash == previous_hash) {
					frappe.router.route();
				}
			}
		});
	}

	add_more_global_table_rows(doctype, results_sets, $trigger, $list) {
		const set_entry = results_sets[0];
		if (
			!set_entry ||
			!set_entry.results ||
			!set_entry.results.length ||
			!$list ||
			!$list.length
		) {
			return;
		}
		const cols = [];
		$list
			.find(".list-row-head .list-row-col")
			.slice(1)
			.each(function () {
				cols.push($(this).find("span").first().text());
			});
		const keywords = this.current_keyword;
		set_entry.results.forEach((r) =>
			this.append_global_result_list_row(
				r,
				cols,
				keywords,
				set_entry.title || doctype,
				$list
			)
		);
		if (set_entry.results.length < this.more_count) {
			$trigger.hide();
			let total_rows = Math.max(0, $list.children(".list-row-container").length - 1);
			const status_word = total_rows === 1 ? __("result") : __("results");
			$('<div class="results-status">')
				.text(`${total_rows} ${status_word}`)
				.insertAfter($trigger);
		}
	}

	add_more_results(results_set) {
		let more_results = $('<div class="more-results last"></div>');
		if (results_set[0].results) {
			results_set[0].results.forEach((result) => {
				more_results.append(this.render_result(results_set[0].title, result));
			});
		}
		this.$body.find(".list-more").before(more_results);

		if (results_set[0].results.length < this.more_count) {
			// hide more button and add a result count
			this.$body.find(".list-more").hide();
			let no_of_results = this.$body.find(".result").length;
			const cue_word = no_of_results === 1 ? __("result") : __("results");
			let no_of_results_cue = $('<div class="results-status">').text(
				`${no_of_results} ${cue_word} ${__("found")}`
			);
			this.$body.find(".more-results:last").append(no_of_results_cue);
		}
		this.$body.find(".more-results.last").slideDown(200, function () {});
	}
};
