frappe.provide("frappe.doctype_settings");

/**
 * PROTOTYPE — shared "list panel" for list-shaped settings tabs.
 *
 * Renders the CRM-style layout: panel header (title + description + a primary
 * "New" action) over a table of rows with an optional inline Switch and a per-row
 * "…" overflow menu. Owns loading / empty / error states so tabs don't repeat them.
 *
 * Slot-based config (fixed visual skeleton: title cell ▸ columns ▸ toggle ▸ actions):
 *
 *   frappe.doctype_settings.render_list(panel, {
 *     title, description,
 *     show_header: false,                     // column-header row off by default; opt in for dense lists
 *     primary_action: { label, icon, onclick(list) },
 *     load: () => Promise<rows[]>,            // or rows: [...]
 *     title_column: { label, primary(row), secondary(row), onclick(row, list),
 *                     tags: (row) => [{ label, color }] },  // inline es-badge tags after the name
 *     columns: [{ label, value(row), badge(row) -> {label,color,icon}|null, align, width }],  // es-badge
 *     toggle: { label, value(row)->0|1, onchange(row, value, list)->Promise, disabled(row) },
 *     actions: (row) => [{ label, icon, danger, onclick(list) }],
 *     empty_state: { title, description, action: { label, onclick(list) } },
 *   }) -> ListController { reload(), refresh_row(row), set_rows(rows), get_rows() }
 */
frappe.doctype_settings.render_list = function (panel, config) {
	const controller = new ListPanel(panel, config);
	controller.init();
	return controller;
};

class ListPanel {
	constructor(panel, config) {
		this.panel = panel;
		this.config = config;
		this.rows = [];
	}

	init() {
		const c = this.config;
		this.panel.set_view({
			title: c.title,
			description: c.description,
			actions: this.header_actions(true),
			render: (p) => {
				this.$body = p.body;
				this.load();
			},
		});
	}

	header_actions(show_primary) {
		const pa = this.config.primary_action;
		if (show_primary && pa) {
			return [{ label: pa.label, icon: pa.icon, click: () => pa.onclick(this) }];
		}
		return [];
	}

	// Re-render just the header; used to hide the top-right primary action when the
	// empty state already offers its own create button (avoids a duplicate "New").
	apply_header(show_primary) {
		this.panel.set_header({
			title: this.config.title,
			description: this.config.description,
			actions: this.header_actions(show_primary),
		});
	}

	load() {
		this.render_state(__("Loading"));
		const c = this.config;
		const source = c.load ? c.load() : Promise.resolve(c.rows || []);
		Promise.resolve(source)
			.then((rows) => {
				this.rows = rows || [];
				this.render();
			})
			.catch(() => this.render_error());
	}

	// ── public controller API ──
	reload() {
		this.load();
	}
	get_rows() {
		return this.rows;
	}
	set_rows(rows) {
		this.rows = rows || [];
		this.render();
	}
	refresh_row(row) {
		// Re-render just one row in place (keeps the rest of the table untouched).
		if (!this._row_els || !this._row_els.has(row)) return this.render();
		const $new = this.make_row(row);
		this._row_els.get(row).replaceWith($new);
		this._row_els.set(row, $new);
	}

	// ── rendering ──
	render() {
		this.$body.empty();
		if (!this.rows.length) return this.render_empty();

		this.apply_header(true);
		const $list = $('<div class="dts-list"></div>').appendTo(this.$body);
		if (this.config.show_header) $list.append(this.make_head());

		this._row_els = new Map();
		this.rows.forEach((row) => {
			const $el = this.make_row(row);
			this._row_els.set(row, $el);
			$list.append($el);
		});
	}

	make_head() {
		const c = this.config;
		const $head = $('<div class="dts-list-row dts-list-head"></div>');

		// The title column owns the leading media, so its header label sits at the
		// column's left edge (above the thumbnail) and the rest stays aligned.
		$('<div class="dts-list-cell dts-list-cell-title"></div>')
			.text(c.title_column?.label || __("Name"))
			.appendTo($head);

		(c.columns || []).forEach((col) => {
			const $cell = $('<div class="dts-list-cell"></div>')
				.text(col.label || "")
				.appendTo($head);
			if (col.width) $cell.css("flex", `0 0 ${col.width}`);
			if (col.align) $cell.css("text-align", col.align);
		});

		if (c.toggle) {
			$('<div class="dts-list-cell dts-list-cell-toggle"></div>')
				.text(c.toggle.label || "")
				.appendTo($head);
		}
		if (c.actions)
			$('<div class="dts-list-cell dts-list-cell-actions"></div>').appendTo($head);

		return $head;
	}

	make_row(row) {
		const c = this.config;
		const $row = $('<div class="dts-list-row"></div>');

		// Title column = (primary / secondary) text.
		const tc = c.title_column || {};
		const $title = $('<div class="dts-list-cell dts-list-cell-title"></div>').appendTo($row);

		const $text = $('<div class="dts-list-text"></div>').appendTo($title);

		// Primary line: name + inline tags (attributes of the row, e.g. Default / Global).
		const $primaryRow = $('<div class="dts-list-primary-row"></div>').appendTo($text);
		const $primary = $('<div class="dts-list-primary ellipsis"></div>')
			.text(tc.primary ? tc.primary(row) : "")
			.appendTo($primaryRow);
		if (tc.onclick) {
			$primary.addClass("dts-list-link").on("click", () => tc.onclick(row, this));
		}

		// Inline tags use the Espresso badge component (color = a badge theme
		// like "green"/"gray").
		const tags = tc.tags ? tc.tags(row) : [];
		tags.forEach((t) =>
			$('<span class="es-badge"></span>')
				.text(t.label)
				.attr("data-theme", t.color || "gray")
				.appendTo($primaryRow)
		);

		if (tc.secondary && tc.secondary(row)) {
			$('<div class="dts-list-secondary"></div>').text(tc.secondary(row)).appendTo($text);
		}

		// Middle columns: text or badge.
		(c.columns || []).forEach((col) => {
			const $cell = $('<div class="dts-list-cell"></div>').appendTo($row);
			if (col.width) $cell.css("flex", `0 0 ${col.width}`);
			if (col.align) $cell.css("text-align", col.align);

			const badge = col.badge && col.badge(row);
			if (badge) {
				const $badge = $('<span class="es-badge"></span>')
					.attr("data-theme", badge.color || "gray")
					.appendTo($cell);
				if (badge.icon) $badge.append(frappe.utils.icon(badge.icon, "sm"));
				$badge.append($("<span></span>").text(badge.label));
			} else if (col.value) {
				$cell.text(col.value(row) || "");
			}
		});

		// Toggle (lightweight switch reusing the ControlSwitch SCSS).
		if (c.toggle) $row.append(this.make_toggle(row));

		// Overflow "…" menu.
		if (c.actions) $row.append(this.make_actions(row));

		return $row;
	}

	make_toggle(row) {
		const t = this.config.toggle;
		const $cell = $('<div class="dts-list-cell dts-list-cell-toggle"></div>');
		const checked = !!t.value(row);
		const disabled = t.disabled ? t.disabled(row) : false;

		const $label = $(`
			<label class="switch-control dts-switch">
				<span class="input-area">
					<input type="checkbox" role="switch" />
				</span>
				<span class="switch-visual" aria-hidden="true"><span class="switch-thumb"></span></span>
			</label>
		`).appendTo($cell);

		const $input = $label.find("input").prop("checked", checked).prop("disabled", disabled);

		// Last confirmed state — advanced on each success so a later failure reverts to the
		// most recent good value, not the one captured at first render.
		let last_good = checked;

		$input.on("change", () => {
			const value = $input.is(":checked") ? 1 : 0;
			$input.prop("disabled", true);
			Promise.resolve(t.onchange(row, value, this))
				.then(() => {
					last_good = !!value;
					$input.prop("disabled", false);
				})
				.catch(() => {
					// Revert to the last confirmed state on failure.
					$input.prop("checked", last_good).prop("disabled", false);
					frappe.show_alert({ message: __("Could not update"), indicator: "red" });
				});
		});

		return $cell;
	}

	make_actions(row) {
		// Bind the controller into each handler, then defer to the shared overflow menu.
		const items = (this.config.actions(row) || []).map((item) => ({
			...item,
			onclick: () => item.onclick(this),
		}));
		return frappe.doctype_settings.overflow_menu(items);
	}

	render_empty() {
		this.$body.empty();
		const e = this.config.empty_state || {};
		// If the empty state offers its own create button, drop the header's primary
		// action so there aren't two "New" buttons.
		this.apply_header(!e.action);
		frappe.doctype_settings.empty_state(this.$body, {
			icon: e.icon,
			title: e.title,
			description: e.description,
			action: e.action && { label: e.action.label, onclick: () => e.action.onclick(this) },
		});
	}

	render_state(text) {
		this.$body.empty();
		$('<div class="text-muted small dts-list-state"></div>').text(text).appendTo(this.$body);
	}

	render_error() {
		this.$body.empty();
		const $err = $('<div class="dts-list-state"></div>').appendTo(this.$body);
		$('<div class="text-muted small"></div>')
			.text(__("Could not load this tab."))
			.appendTo($err);
		frappe.ui
			.button({ label: __("Retry"), size: "xs", onclick: () => this.load() })
			.appendTo($err);
	}
}
