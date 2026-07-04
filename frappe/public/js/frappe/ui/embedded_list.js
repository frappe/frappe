// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See LICENSE

frappe.provide("frappe.ui");

frappe.ui.EmbeddedList = class EmbeddedList {
	constructor(opts) {
		Object.assign(
			this,
			{
				page_size: 50,
				empty_message: __("No records found."),
				loading_message: __("Loading..."),
				error_message: __("Failed to load data."),
				columns: [],
				filters: {},
				fields: ["name"],
				order_by: null,
			},
			opts
		);

		// `wrapper` may be a jQuery object or a raw element.
		this.$wrapper = this.wrapper instanceof jQuery ? this.wrapper : $(this.wrapper);

		this.data = [];
		this.rendered_count = 0;

		this.make();
	}

	make() {
		this.$wrapper.addClass("embedded-list");
		this.$header = $('<div class="embedded-list-header"></div>').appendTo(this.$wrapper);
		this.$loading = $(
			`<div class="embedded-list-loading text-muted">${this.loading_message}</div>`
		)
			.appendTo(this.$wrapper)
			.hide();
		this.$error = $(`<div class="embedded-list-error text-danger"></div>`)
			.appendTo(this.$wrapper)
			.hide();
		this.$result = $(`<div class="embedded-list-result"></div>`)
			.appendTo(this.$wrapper)
			.hide();
		this.$no_result = $(
			`<div class="embedded-list-no-result text-muted">${this.empty_message}</div>`
		)
			.appendTo(this.$wrapper)
			.hide();

		this.render_header();
		this.bind_events();
	}

	// Header: title + description on the left, an optional Add button on the
	// right. Always visible (so rows can be added even when the list is empty).
	render_header() {
		const title = this.title ? `<div class="embedded-list-title">${this.title}</div>` : "";
		const description = this.description
			? `<div class="embedded-list-description">${this.description}</div>`
			: "";
		const add = this.add_button
			? frappe.ui.button.html({
					label: this.add_button.label || __("Add"),
					attrs: { "data-action": "add-row" },
			  })
			: "";
		const search = `<input type="text" class="form-control form-control-sm embedded-list-search" data-action="search" placeholder="${__(
			"Search"
		)}">`;

		if (!title && !description && !add) {
			this.$header.hide();
			return;
		}
		this.$header.html(
			`<div class="embedded-list-heading">${title}${description}</div>
			<div class="embedded-list-header-actions">${search}${add}</div>`
		);
	}

	// --- Data ---

	// Override `get_args` to customise the query without replacing `get_data`.
	get_args() {
		return {
			filters: this.filters,
			fields: this.fields,
			order_by: this.order_by,
			limit: 0,
		};
	}

	// Override `get_data` for multi-doctype / merge logic. Must return a Promise
	// that resolves to an array of row objects.
	get_data() {
		if (!this.doctype) {
			// eslint-disable-next-line no-console
			console.error("EmbeddedList: set `doctype` or override `get_data()`.");
			return Promise.resolve([]);
		}
		return frappe.db.get_list(this.doctype, this.get_args());
	}

	refresh() {
		this.$error.hide();
		this.$result.hide();
		this.$no_result.hide();
		this.$loading.show();

		return this.get_data()
			.then((data) => {
				this._all_data = data || [];
				this.$loading.hide();
				this.before_render();
				this._apply_filter();
			})
			.catch((e) => {
				// eslint-disable-next-line no-console
				console.error("EmbeddedList: failed to load data", e);
				this.$loading.hide();
				this.$error.text(this.error_message).show();
			});
	}

	_apply_filter() {
		const term = (this.$wrapper.find("[data-action='search']").val() || "")
			.trim()
			.toLowerCase();
		this.data = term
			? this._all_data.filter((row) =>
					Object.values(row).some(
						(val) => val != null && String(val).toLowerCase().includes(term)
					)
			  )
			: [...this._all_data];
		this.rendered_count = 0;
		this.render();
		this.after_render();
		this.toggle_result_area();
	}

	before_render() {}
	after_render() {}

	render() {
		this.rendered_count = 0;
		this.$result.empty();

		if (!this.data.length) return;

		// The table sits inside a rounded, bordered container; the footer
		// (load-more / count) sits outside it.
		const $wrap = $('<div class="embedded-list-table-wrap"></div>');
		const $table = $(`
			<table class="embedded-list-table">
				<thead>${this.build_header_html()}</thead>
				<tbody></tbody>
			</table>
		`);
		$wrap.append($table).appendTo(this.$result);
		this.$tbody = $table.find("tbody");

		this.render_more();
	}

	render_more() {
		const next = this.data.slice(this.rendered_count, this.rendered_count + this.page_size);
		const rows_html = next
			.map((row, i) => this.build_row_html(row, this.rendered_count + i))
			.join("");
		this.$tbody.append(rows_html);
		this.rendered_count += next.length;
		this.render_load_more();
	}

	render_load_more() {
		this.$result.find(".embedded-list-more").remove();
		if (this.rendered_count >= this.data.length) return;

		const remaining = this.data.length - this.rendered_count;
		const count = Math.min(remaining, this.page_size);
		$(
			`<div class="embedded-list-more">
				<span class="embedded-list-count">${__("Showing {0} of {1}", [
					this.rendered_count,
					this.data.length,
				])}</span>
				${frappe.ui.button.html({ label: __("Load More"), attrs: { "data-action": "load-more" } })}
			</div>`
		).appendTo(this.$result);
	}

	build_header_html() {
		let cells = this.columns
			.map((col) => {
				const label = frappe.utils.escape_html(col.label || "");
				const title = col.title ? ` title="${frappe.utils.escape_html(col.title)}"` : "";
				const align = col.align === "center" ? ' class="text-center"' : "";
				return `<th${align}${title}>${label}</th>`;
			})
			.join("");
		if (this.show_index) {
			cells = `<th class="embedded-list-index">${__("No.")}</th>` + cells;
		}
		return `<tr>${cells}</tr>`;
	}

	build_row_html(row, index) {
		const clickable = this.on_row_click ? ' style="cursor: pointer;"' : "";
		let cells = this.columns
			.map((col, col_idx) => this.build_cell_html(col, col_idx, row))
			.join("");
		if (this.show_index) {
			cells = `<td class="embedded-list-index">${index + 1}</td>` + cells;
		}
		return `<tr data-row-idx="${index}"${clickable}>${cells}</tr>`;
	}

	build_cell_html(col, col_idx, row) {
		const align = col.align === "center" ? ' class="text-center"' : "";
		const clickable = typeof col.on_click === "function";
		const col_attr = clickable
			? ` data-col-idx="${col_idx}" class="embedded-list-clickable"`
			: "";

		if (col.type === "actions") {
			return `<td class="text-center embedded-list-actions" data-col-idx="${col_idx}">${this.build_actions_html(
				col
			)}</td>`;
		}

		if (typeof col.render === "function") {
			return `<td${align}${col_attr}>${col.render(row) ?? ""}</td>`;
		}

		const raw = col.fieldname ? row[col.fieldname] : "";

		if (col.type === "check") {
			return `<td class="text-center"${col_attr}>${
				raw ? frappe.utils.icon("check", "xs") : ""
			}</td>`;
		}

		if (col.type === "badge") {
			if (raw == null || raw === "") return `<td${align}${col_attr}></td>`;
			const color = typeof col.color === "function" ? col.color(row) : col.color || "gray";
			return `<td${align}${col_attr}><span class="es-badge" data-theme="${color}">${frappe.utils.escape_html(
				raw
			)}</span></td>`;
		}

		if (col.type === "link") {
			// `text(row)` lets the label be computed (e.g. a fallback); otherwise
			// the field value is used.
			const label = typeof col.text === "function" ? col.text(row) : raw;
			const text = frappe.utils.escape_html(label ?? "");
			if (col.url) {
				return `<td${align}><a href="${col.url(
					row
				)}" onclick="event.stopPropagation();">${text}</a></td>`;
			}
			// Route-based link: the delegated handler navigates and stops
			// propagation itself, so no inline onclick (which would prevent the
			// event from reaching that handler).
			return `<td${align}><a href="#" data-route-link="${col_idx}">${text}</a></td>`;
		}

		return `<td${align}${col_attr}>${frappe.utils.escape_html(raw ?? "")}</td>`;
	}

	build_actions_html(col) {
		return (col.actions || [])
			.map((action, action_idx) =>
				// only danger actions take the red theme, others stay neutral gray
				frappe.ui.button.html({
					label: action.icon ? "" : action.label || "",
					icon: action.icon,
					size: "xs",
					variant: "ghost",
					theme: action.danger ? "red" : null,
					title: action.label,
					attrs: { "data-action-idx": String(action_idx) },
				})
			)
			.join("");
	}

	// --- Events ---

	bind_events() {
		// Namespaced + unbound first so re-instantiating on the same wrapper
		// (e.g. on every form refresh) does not stack duplicate handlers.
		this.$wrapper.off(".embedded_list");

		// Search
		this.$wrapper.on("input.embedded_list", "[data-action='search']", () => {
			this._apply_filter();
		});

		// Add row
		this.$wrapper.on("click.embedded_list", "[data-action='add-row']", (e) => {
			e.preventDefault();
			if (this.add_button && this.add_button.action) {
				this.add_button.action(() => this.refresh());
			}
		});

		// Load more
		this.$wrapper.on("click.embedded_list", "[data-action='load-more']", (e) => {
			e.preventDefault();
			this.render_more();
		});

		// Row actions
		this.$wrapper.on(
			"click.embedded_list",
			".embedded-list-actions [data-action-idx]",
			(e) => {
				e.preventDefault();
				e.stopPropagation();
				const $btn = $(e.currentTarget);
				const row = this.row_for(e);
				const col = this.columns[parseInt($btn.closest("td").attr("data-col-idx"), 10)];
				if (!col) return;
				const action = col.actions[parseInt($btn.attr("data-action-idx"), 10)];
				if (action) this.run_action(action, row);
			}
		);

		// Clickable cells (custom on_click)
		this.$wrapper.on("click.embedded_list", "td.embedded-list-clickable", (e) => {
			e.preventDefault();
			e.stopPropagation();
			const col = this.columns[parseInt($(e.currentTarget).attr("data-col-idx"), 10)];
			if (col && typeof col.on_click === "function") col.on_click(this.row_for(e));
		});

		// Route-based links
		this.$wrapper.on("click.embedded_list", "a[data-route-link]", (e) => {
			e.preventDefault();
			e.stopPropagation();
			const col = this.columns[parseInt($(e.currentTarget).attr("data-route-link"), 10)];
			if (col && col.route) frappe.set_route(...col.route(this.row_for(e)));
		});

		// Whole-row click
		this.$wrapper.on("click.embedded_list", "tr[data-row-idx]", (e) => {
			if (!this.on_row_click) return;
			this.on_row_click(this.row_for(e));
		});
	}

	// Resolve the data row for an event by walking up to the <tr>.
	row_for(e) {
		const idx = parseInt($(e.currentTarget).closest("tr").attr("data-row-idx"), 10);
		return this.data[idx];
	}

	run_action(action, row) {
		const refresh = () => this.refresh();
		const run = () =>
			Promise.resolve(action.action(row, refresh)).catch((e) => {
				frappe.msgprint({
					title: __("Error"),
					message: (e && e.message) || __("Action failed."),
					indicator: "red",
				});
			});
		if (action.confirm) {
			const label = action.confirm_field ? row[action.confirm_field] : "";
			frappe.confirm(__(action.confirm, [label]), run);
		} else {
			run();
		}
	}

	toggle_result_area() {
		this.$result.toggle(this.data.length > 0);
		this.$no_result.toggle(this.data.length === 0);
	}
};
