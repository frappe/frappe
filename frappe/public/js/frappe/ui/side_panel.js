// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui");

// Right-side overlay drawer previewing a document in a frm-less frappe.ui.form.Layout — the same
// construction every Dialog uses, so no cur_frm, realtime subscriptions or client scripts.

const TABLE_FIELDTYPES = ["Table", "Table MultiSelect"];

const SIDE_PANEL_WIDTH_KEY = "side_panel_width";
const LOAD_TIMEOUT_MS = 20000;

// Fails open: showing an extra field beats hiding one the user should see.
function passes_depends_on(expression, doc, parent) {
	if (!expression) return true;
	if (typeof expression === "boolean") return expression;
	if (typeof expression === "function") {
		try {
			return Boolean(expression(doc));
		} catch (e) {
			return true;
		}
	}
	if (expression.startsWith("eval:")) {
		try {
			return Boolean(frappe.utils.eval(expression.substr(5), { doc, parent }));
		} catch (e) {
			return true;
		}
	}
	if (expression.startsWith("fn:")) return true; // script-driven; scripts never run here
	const value = doc[expression];
	return Array.isArray(value) ? value.length > 0 : Boolean(value);
}

function get_read_only_docfields(doctype) {
	const meta = frappe.get_meta(doctype);

	return (meta?.fields || []).map((df) => {
		const clone = { ...df, parent: df.parent || doctype, read_only: 1 };

		// Frm-less, Grid.setup_fields() reads child docfields from df.fields, not the parent meta.
		if (TABLE_FIELDTYPES.includes(df.fieldtype) && df.options) {
			clone.fields = get_read_only_docfields(df.options);
		}

		return clone;
	});
}

// Child rows render as static formatted values — live controls need a frm/doc for formatting,
// link navigation, validation and fetches, none of which exist here.

const STATIC_SKIP_FIELDTYPES = new Set([
	"Section Break",
	"Column Break",
	"Tab Break",
	"HTML",
	"Button",
	"Fold",
	"Heading",
	"Table",
	"Table MultiSelect",
]);

// Only fieldtypes that can't carry arbitrary strings are trusted with the formatter's raw HTML;
// everything else is escaped.
const STATIC_SAFE_HTML_FIELDTYPES = new Set([
	"Currency",
	"Int",
	"Float",
	"Percent",
	"Duration",
	"Date",
	"Datetime",
	"Time",
	"Rating",
]);

function render_static_field_value($value_el, df, doc) {
	const raw = doc[df.fieldname];

	if (df.fieldtype === "Link" || df.fieldtype === "Dynamic Link") {
		if (raw == null || raw === "") return;
		const link_doctype = df.fieldtype === "Dynamic Link" ? doc[df.options] : df.options;
		if (!link_doctype || !frappe.model.can_read(link_doctype)) {
			$value_el.text(String(raw));
			return;
		}
		// createElement + innerText so the title can never inject markup.
		const a = document.createElement("a");
		a.href = `/app/${frappe.router.slug(link_doctype)}/${encodeURIComponent(raw)}`;
		a.dataset.doctype = link_doctype;
		a.dataset.name = raw;
		a.innerText = frappe.utils.get_link_title(link_doctype, raw) || raw;
		$value_el.append(a);
		return;
	}

	if (df.fieldtype === "Check") {
		$value_el.html(
			`<input type="checkbox" disabled class="disabled-${
				cint(raw) ? "selected" : "deselected"
			}">`
		);
		return;
	}

	if (STATIC_SAFE_HTML_FIELDTYPES.has(df.fieldtype)) {
		const formatted = frappe.format(raw, df, { no_icon: true, only_value: true }, doc);
		$value_el.html(formatted == null ? "" : formatted);
		return;
	}

	// Escape everything, then restore only literal <br> line breaks from stored template text.
	const escaped = frappe.utils.escape_html(raw == null ? "" : String(raw));
	$value_el.html(escaped.replace(/&lt;br\s*\/?&gt;/gi, "<br>"));
}

// Reuses the form's own classes (.form-section, .control-label, .like-disabled-input) so it
// inherits form.scss directly. `parent` is what a child-row depends_on "eval:" sees as `parent`.
function render_static_doc_fields(container_el, doctype, doc, parent) {
	const meta = frappe.get_meta(doctype);
	const $root = $('<div class="side-panel-detail form-layout"></div>').appendTo(container_el);
	// Child doctypes carry no perms of their own, so permlevels resolve against the parent.
	const perm = frappe.perm.get_perm(parent?.doctype || doctype, parent || doc);

	let $section = null;
	let $columns = null;
	let $column = null;
	let section_ok = true;

	const break_visible = (df) => !df.depends_on || passes_depends_on(df.depends_on, doc, parent);

	const open_section = (label, ok) => {
		section_ok = ok;
		if (!ok) return;
		$section = $('<div class="form-section card-section"></div>').appendTo($root);
		if (label) $('<div class="section-head"></div>').text(__(label)).appendTo($section);
		$columns = $('<div class="section-body side-panel-detail-columns"></div>').appendTo(
			$section
		);
		$column = null;
	};
	const open_column = () => {
		if (!$section) open_section(null, true);
		$column = $('<div class="form-column side-panel-detail-column"></div>').appendTo($columns);
	};

	for (const df of meta?.fields || []) {
		if (df.fieldtype === "Tab Break") continue; // flatten tabs into one scroll
		if (df.fieldtype === "Section Break") {
			open_section(df.label, break_visible(df));
			continue;
		}
		if (!section_ok) continue;
		if (df.fieldtype === "Column Break") {
			open_column();
			continue;
		}
		if (STATIC_SKIP_FIELDTYPES.has(df.fieldtype)) continue;
		if (df.hidden) continue;
		if (frappe.perm.get_field_display_status(df, doc, perm) === "None") continue;
		if (df.depends_on && !passes_depends_on(df.depends_on, doc, parent)) continue;

		if (!$column) open_column();
		// Mirrors base_input.js's make_wrapper so values get the disabled-control pill.
		const $field = $('<div class="frappe-control"></div>').appendTo($column);
		const $group = $('<div class="form-group"></div>').appendTo($field);
		$('<label class="control-label"></label>')
			.text(__(df.label || df.fieldname))
			.appendTo($group);
		const $value = $('<div class="control-value like-disabled-input"></div>').appendTo($group);
		render_static_field_value($value, df, doc);
	}

	// Drop sections left empty by hidden / depends_on-false fields.
	$root.find(".form-section").each(function () {
		if (!$(this).find(".frappe-control").length) $(this).remove();
	});
}

frappe.ui.SidePanel = class SidePanel {
	constructor() {
		// One Layout per doctype; refresh(doc) repoints it at a different document.
		this.layouts = {};
		// [doctype, docname] pairs of child-row docfield copies seeded by this preview.
		this.cached_child_docfields = [];
		this.history = [];
		// Bumped on every open() so a slow with_doc can't paint over newer content.
		this.token = 0;
		this.current = null;
		this.make();
	}

	make() {
		this.$panel = $(frappe.render_template("side_panel", {})).appendTo(document.body);

		this.$body = this.$panel.find(".side-panel-body");
		this.setup_resize();

		this.$panel.find(".side-panel-back").on("click", () => this.back());

		this.$panel.find(".side-panel-expand").on("click", () => {
			const current = this.current;
			this.close();
			if (current) frappe.set_route("Form", current.doctype, current.docname);
		});

		this.$panel.find(".side-panel-close").on("click", () => this.close());

		// Links drill into their target in the drawer. stopPropagation keeps the router's
		// delegated <a> handler on <body> from routing the page away.
		this.$body.on("click", "a[data-doctype][data-name]", (e) => {
			if (e.which !== 1 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
			e.preventDefault();
			e.stopPropagation();
			const { doctype, name } = e.currentTarget.dataset;
			this.open(doctype, name);
		});

		frappe.router.on("change", () => this.close());

		$(document).on("keydown.side-panel", (e) => {
			if (e.key !== "Escape" || !this.is_open()) return;
			// A dialog or open grid row sits on top of the panel; Escape belongs to it.
			if ($(".modal:visible, .grid-row-open").length) return;
			this.close();
		});
	}

	// Width lives in --side-panel-width, which the closed offset derives from too, so the drawer
	// still tucks fully off-screen at any width.
	setup_resize() {
		const stored = parseInt(localStorage.getItem(SIDE_PANEL_WIDTH_KEY), 10);
		if (stored) this.set_width(stored);

		this.$panel.find(".side-panel-resizer").on("mousedown", (e) => {
			// CSS hides the handle below the mobile breakpoint; don't restate the breakpoint here.
			if (!$(e.currentTarget).is(":visible")) return;
			e.preventDefault();

			const start_x = e.clientX;
			const start_width = this.$panel.outerWidth();

			// Kills the slide transition for the drag, else it trails the cursor by 200ms.
			$("body").addClass("side-panel-resizing");

			const on_move = (move_event) => {
				this.set_width(start_width + (start_x - move_event.clientX));
			};

			const on_up = () => {
				$(document).off("mousemove.side-panel-resize mouseup.side-panel-resize");
				$("body").removeClass("side-panel-resizing");
				localStorage.setItem(SIDE_PANEL_WIDTH_KEY, this.$panel.outerWidth());
			};

			$(document)
				.on("mousemove.side-panel-resize", on_move)
				.on("mouseup.side-panel-resize", on_up);
		});

		// Double-click resets to the default width.
		this.$panel.find(".side-panel-resizer").on("dblclick", () => {
			this.$panel[0].style.removeProperty("--side-panel-width");
			localStorage.removeItem(SIDE_PANEL_WIDTH_KEY);
		});

		// set_width() clamps against the viewport, so a stored width from a larger window would
		// otherwise overhang until the next drag.
		$(window).on(
			"resize.side-panel",
			frappe.utils.debounce(() => {
				const width = parseInt(
					this.$panel[0].style.getPropertyValue("--side-panel-width"),
					10
				);
				if (width) this.set_width(width);
			}, 100)
		);
	}

	set_width(width) {
		// Lower bound comes from --side-panel-min-width so it can't drift from the CSS clamp.
		const min =
			parseInt(
				getComputedStyle(this.$panel[0]).getPropertyValue("--side-panel-min-width"),
				10
			) || 0;
		const max = Math.max(min, window.innerWidth - 120);
		const clamped = Math.min(Math.max(width, min), max);
		this.$panel[0].style.setProperty("--side-panel-width", `${clamped}px`);
	}

	open(doctype, docname, { push = true } = {}) {
		if (!doctype || !docname) return;

		if (!frappe.model.can_read(doctype)) {
			frappe.show_alert({
				message: __("Not permitted to view {0}", [__(doctype)]),
				indicator: "orange",
			});
			return;
		}

		// Re-clicking the open document shouldn't rebuild it or stack up history.
		if (
			this.is_open() &&
			this.current &&
			this.current.doctype === doctype &&
			this.current.docname === docname
		) {
			return;
		}

		if (push && this.current) this.history.push(this.current);
		this.current = { doctype, docname };
		this.show();
		this.render();
	}

	back() {
		const previous = this.history.pop();
		if (!previous) return;
		this.current = previous;
		this.render();
	}

	render() {
		const { doctype, docname } = this.current;
		const token = ++this.token;

		this.$panel.find(".side-panel-back").toggleClass("hidden", !this.history.length);
		this.set_header(doctype, docname, null);
		this.set_state("loading");

		// with_doctype/with_doc wrap frappe.call, whose callback only runs on success, and their
		// promises never reject — so a failed request would otherwise hang on "Loading" forever.
		const timeout = new Promise((_, reject) => setTimeout(reject, LOAD_TIMEOUT_MS));

		const load = frappe.model
			.with_doctype(doctype)
			.then(() => frappe.model.with_doc(doctype, docname));

		Promise.race([load, timeout])
			.then(() => {
				if (token !== this.token) return;
				if (!frappe.get_doc(doctype, docname)) throw new Error("not loaded");

				this.render_doc(doctype, docname);
				this.set_header(doctype, docname, frappe.get_doc(doctype, docname));
				this.set_state("ready");
			})
			.catch((e) => {
				if (token !== this.token) return;
				console.error("[side panel] failed to render", doctype, docname, e);
				this.set_state("error");
			});
	}

	render_doc(doctype, docname) {
		const doc = frappe.get_doc(doctype, docname);
		let entry = this.layouts[doctype];

		if (!entry) {
			const $wrapper = $('<div class="side-panel-doc">').appendTo(this.$body);
			const layout = new frappe.ui.form.Layout({
				parent: $wrapper,
				doctype: doctype,
				// Explicit fields also avoid get_doctype_fields(), which needs a frm.
				fields: get_read_only_docfields(doctype),
				doc: doc,
				card_layout: true,
			});
			layout.make();
			entry = this.layouts[doctype] = { layout, $wrapper };
		}

		this.$body.find(".side-panel-doc").addClass("hidden");
		entry.$wrapper.removeClass("hidden");

		entry.layout.doc = doc;
		this.prepare_grids(entry.layout, doc);
		entry.layout.refresh(doc);
		this.enforce_read_only(entry.layout);
		// refresh() rebuilds grid_rows, so the rows to bind only exist now.
		this.make_rows_openable(entry.layout);
	}

	// attach_doc_and_docfields() swaps each control's df for the live metadata copy on every
	// refresh, so read_only is re-applied here — onto a per-control clone, never the shared meta.
	// Control.perm can't be used: its setter is a no-op that reads frm.perm (base_control.js).
	enforce_read_only(layout) {
		for (const field of layout.fields_list || []) {
			if (!field.df || cint(field.df.read_only)) continue;
			field.df = { ...field.df, read_only: 1 };
			field.refresh?.();
		}
	}

	// Rows open in a plain Dialog; grid_row_form is an editing surface that needs a live frm.
	make_rows_openable(layout) {
		for (const field of layout.fields_list || []) {
			const child_doctype = field.df?.options;
			if (!child_doctype) continue;

			for (const row of field.grid?.grid_rows || []) {
				if (!row.doc || !row.row) continue;

				// set_docfields() caches a per-row copy from our read-only clones, keyed by the
				// real row name — the routed form would inherit it. Track it so close() drops it.
				if (frappe.meta.docfield_copy[child_doctype]?.[row.doc.name]) {
					this.cached_child_docfields.push([child_doctype, row.doc.name]);
				}

				if (row.__side_panel_bound) continue;
				row.__side_panel_bound = true;

				row.row.css("cursor", "pointer").on("click", (e) => {
					// The row's own links/checkboxes keep their behaviour.
					if ($(e.target).closest("a, button, input").length) return;
					this.open_row_dialog(child_doctype, row.doc);
				});
			}
		}
	}

	open_row_dialog(child_doctype, row_doc) {
		this.row_dialog?.hide();

		const parent_doc =
			this.current && frappe.get_doc(this.current.doctype, this.current.docname);

		const dialog = new frappe.ui.Dialog({
			title: __("Row #{0}", [row_doc.idx]),
			size: "extra-large",
		});
		this.row_dialog = dialog;
		dialog.$wrapper.addClass("side-panel-row-dialog");

		// Read-only: no action to offer.
		dialog.get_primary_btn().hide();

		render_static_doc_fields(dialog.body, child_doctype, row_doc, parent_doc);

		$(dialog.body).on("click", "a[data-doctype][data-name]", (e) => {
			if (e.which !== 1 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
			e.preventDefault();
			const { doctype, name } = e.currentTarget.dataset;
			dialog.hide();
			this.open(doctype, name);
		});

		dialog.show();
	}

	// Drop seeded copies so the routed form rebuilds from untouched metadata.
	clear_cached_child_docfields() {
		for (const [doctype, docname] of this.cached_child_docfields) {
			delete frappe.meta.docfield_copy[doctype]?.[docname];
		}
		this.cached_child_docfields = [];
	}

	// Frm-less, a grid reads rows from df.data (nothing populates it) and hardcodes
	// display_status "Write", so read-only has to come from static_rows.
	prepare_grids(layout, doc) {
		for (const field of layout.fields_list || []) {
			const grid = field.grid;
			if (!grid) continue;

			const rows = doc[field.df.fieldname] || [];
			field.df.data = rows;
			// setup_fields() can swap grid.df for a child-doctype docfield; keep both in step.
			if (grid.df && grid.df !== field.df) grid.df.data = rows;

			grid.static_rows = true;
		}
	}

	set_header(doctype, docname, doc) {
		this.$panel.find(".side-panel-doctype").text(__(doctype));
		this.$panel.find(".side-panel-title").text(docname);

		const $indicator = this.$panel.find(".side-panel-indicator").empty();
		const indicator = doc ? frappe.get_indicator(doc, doctype) : null;
		if (indicator) {
			// badge-legacy-colors.css maps arbitrary indicator colour names onto es-badge themes.
			$indicator.append(
				$('<span class="es-badge">').attr("data-theme", indicator[1]).text(indicator[0])
			);
		}
	}

	set_state(state) {
		this.$body.find(".side-panel-message").remove();
		this.$panel.toggleClass("is-loading", state === "loading");
		this.$body.find(".side-panel-doc").toggleClass("invisible", state !== "ready");

		const message =
			state === "loading"
				? __("Loading...")
				: state === "error"
				? __("Could not load this document")
				: null;

		if (message) {
			$('<div class="side-panel-message text-center text-extra-muted"></div>')
				.text(message)
				.appendTo(this.$body);
		}
	}

	show() {
		this.$panel.removeClass("hidden");
		// Next frame, so the slide has a start state to animate from.
		requestAnimationFrame(() => this.$panel.addClass("is-open"));
		$("body").addClass("side-panel-open");
	}

	is_open() {
		return this.$panel.hasClass("is-open");
	}

	close() {
		if (!this.is_open()) return;
		this.token++; // abandon any in-flight render
		this.$panel.removeClass("is-open").addClass("hidden");
		$("body").removeClass("side-panel-open");
		this.history = [];
		this.current = null;
		this.row_dialog?.hide();
		this.clear_cached_child_docfields();
	}
};

// Lazy singleton.
frappe.ui.get_side_panel = function () {
	if (!frappe.ui._side_panel) {
		frappe.ui._side_panel = new frappe.ui.SidePanel();
	}
	return frappe.ui._side_panel;
};

// Off on mobile, where the drawer would cover the whole viewport and routing to the form is the
// better experience. Defaults on, so an unset flag (pre-migration boot) still previews.
frappe.ui.split_view_enabled = function () {
	if (frappe.is_mobile()) return false;
	const enabled = frappe.boot.desk_settings?.report_split_view;
	return enabled === undefined || cint(enabled) === 1;
};

// Previews a clicked Link cell instead of routing to it. `is_link_cell` is the caller's policy —
// report view keeps a docfield on the column, query reports put fieldtype/options on it directly.
frappe.ui.handle_link_cell_click = function (e, is_link_cell) {
	if (!frappe.ui.split_view_enabled()) return false;
	if (e.which !== 1 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return false;

	const link = e.currentTarget;
	const { doctype, name } = link.dataset;
	if (!doctype || !name) return false;

	if (is_link_cell && !is_link_cell($(link).closest(".dt-cell"))) return false;

	e.preventDefault();
	// stopPropagation keeps router.js's delegated <a> handler on <body> from routing away.
	e.stopPropagation();

	frappe.ui.get_side_panel().open(doctype, name);
	return true;
};
