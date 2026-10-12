// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui");

// Right-side overlay drawer previewing a document in a frm-less frappe.ui.form.Layout — the same
// construction every Dialog uses, so no cur_frm, realtime subscriptions or client scripts.

const TABLE_FIELDTYPES = ["Table", "Table MultiSelect"];

const SIDE_PANEL_WIDTH_KEY = "side_panel_width";
const LOAD_TIMEOUT_MS = 20000;

// A broken expression shows the field rather than breaking the preview.
function passes_depends_on(expression, doc, parent) {
	if (expression.startsWith("eval:")) {
		try {
			return Boolean(frappe.utils.eval(expression.substr(5), { doc, parent }));
		} catch (e) {
			return true;
		}
	}
	if (expression.startsWith("fn:")) return false; // needs a frm to run
	const value = doc[expression];
	return Array.isArray(value) ? value.length > 0 : Boolean(value);
}

function read_only_status(control) {
	if (cint(control.df.hidden) || cint(control.df.hidden_due_to_dependency)) return "None";
	const permlevels = control.layout?.side_panel_permlevels;
	if (permlevels && !permlevels.includes(cint(control.df.permlevel))) return "None";
	return "Read";
}

function force_read_only(fields_list) {
	for (const control of fields_list || []) {
		control.get_status = () => read_only_status(control);
	}
}

function get_read_only_docfields(doctype) {
	return (frappe.get_meta(doctype)?.fields || []).map((df) => {
		const clone = { ...df, parent: df.parent || doctype };

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
function render_static_doc_fields(container_el, doctype, doc, parent, preview) {
	const meta = frappe.get_meta(doctype);
	const $root = $('<div class="side-panel-detail form-layout"></div>').appendTo(container_el);
	// Child doctypes carry no perms of their own; the parent's permlevels come from the preview.
	const permlevels = (preview?.permlevels || []).map(cint);

	let $section = null;
	let $columns = null;
	let $column = null;
	let section_ok = true;

	const break_visible = (df) => !df.depends_on || passes_depends_on(df.depends_on, doc, parent);

	const open_section = (label, ok) => {
		section_ok = ok;
		if (!ok) return;
		$section = $('<div class="form-section"></div>').appendTo($root);
		if (label) $('<div class="section-head"></div>').text(__(label)).appendTo($section);
		$columns = $('<div class="section-body side-panel-detail-columns"></div>').appendTo(
			$section
		);
		$column = null;
	};
	const open_column = () => {
		if (!$section) open_section(null, true);
		$column = $('<div class="form-column side-panel-detail-column flex-1"></div>').appendTo(
			$columns
		);
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
		if (!permlevels.includes(cint(df.permlevel))) continue;
		if (df.depends_on && !passes_depends_on(df.depends_on, doc, parent)) continue;

		if (!$column) open_column();

		// A Check renders as checkbox + inline label, not label-above-a-pill — see
		// ControlCheck.make_wrapper.
		if (df.fieldtype === "Check") {
			const $field = $(`
				<div class="form-group frappe-control">
					<div class="checkbox">
						<label>
							<span class="input-area"><input type="checkbox" disabled></span>
							<span class="label-area"></span>
						</label>
					</div>
				</div>
			`).appendTo($column);
			$field.find("input").prop("checked", Boolean(cint(doc[df.fieldname])));
			$field.find(".label-area").text(__(df.label || df.fieldname));
			continue;
		}

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

const SKELETON_SKIP_FIELDTYPES = new Set(["HTML", "Button", "Fold", "Heading"]);
const SKELETON_TALL_FIELDTYPES = new Set([
	"Text",
	"Small Text",
	"Long Text",
	"Text Editor",
	"Markdown Editor",
	"HTML Editor",
	"Code",
	"JSON",
]);

const bar = (width, height, css_class) => frappe.ui.skeleton.html({ width, height, css_class });

// Real text where we know it, a bar where we don't.
function text_or_bar(label, width) {
	return label ? frappe.utils.escape_html(__(label)) : bar(width, "12px");
}

// Heading row with the child table's list-view columns, then two placeholder rows. Row count
// and column widths are only known once the document arrives.
function skeleton_table(df) {
	const child = frappe.get_meta(df.options);
	const columns = (child?.fields || [])
		.filter((f) => cint(f.in_list_view) && !cint(f.hidden))
		.slice(0, 5);
	const head = columns.length
		? columns
				.map((f) => `<div class="skeleton-grid-col">${text_or_bar(f.label, "60%")}</div>`)
				.join("")
		: `<div class="skeleton-grid-col">${bar("60%", "12px")}</div>`.repeat(3);
	const cells = `<div class="skeleton-grid-col">${bar("60%", "12px")}</div>`.repeat(
		columns.length || 3
	);
	const row = `<div class="skeleton-grid-row"><div class="skeleton-grid-index"></div>${cells}</div>`;
	return `<div class="skeleton-grid">
		<div class="skeleton-grid-head"><div class="skeleton-grid-index">${__("No.")}</div>${head}</div>
		${row.repeat(2)}
	</div>`;
}

function skeleton_field(df) {
	// Same rule as base_input.js: a description shows under the field unless it is set to
	// open on click. Descriptions are meta text, so they render as HTML like the real ones.
	const description =
		df.description && !df.show_description_on_click
			? `<div class="skeleton-help text-extra-muted">${__(
					df.description,
					null,
					df.parent
			  )}</div>`
			: "";
	// Table labels carry no marker in the form (the grid draws its own label).
	const reqd = cint(df.reqd) && df.fieldtype !== "Table" ? " reqd" : "";

	// Checkbox labels carry no required marker in the form either.
	if (df.fieldtype === "Check") {
		return `<div class="skeleton-field">
			<div class="skeleton-check"><input type="checkbox" disabled><span>${text_or_bar(
				df.label,
				"40%"
			)}</span></div>
			${description}
		</div>`;
	}
	let value;
	if (df.fieldtype === "Table") value = skeleton_table(df);
	else if (SKELETON_TALL_FIELDTYPES.has(df.fieldtype)) value = bar("100%", "72px");
	else value = bar("100%", "28px");
	return `<div class="skeleton-field">
		<div class="skeleton-label${reqd}">${text_or_bar(df.label, "30%")}</div>
		${value}
		${description}
	</div>`;
}

// Same tabs, sections and columns as the form that replaces it, sized like the real controls,
// so the crossfade lands on matching boxes. Without a meta it is a plain stack of fields.
function skeleton_form(meta) {
	if (!meta?.fields) {
		const column = (n) => `<div class="flex-1 min-w-0">${skeleton_field({}).repeat(n)}</div>`;
		const section = (n) =>
			`<div class="skeleton-section"><div class="skeleton-columns">${column(n)}${column(
				n
			)}</div></div>`;
		return section(3) + section(2);
	}

	// Without the document a depends_on cannot be judged, so those fields are left out; the
	// form adds them once it lands.
	const skip = (df) =>
		SKELETON_SKIP_FIELDTYPES.has(df.fieldtype) || cint(df.hidden) || Boolean(df.depends_on);

	// The form opens on its first tab; a first field that is not a Tab Break starts one too.
	const tab_labels = meta.fields
		.filter((df) => df.fieldtype === "Tab Break")
		.map((df) => df.label);
	if (meta.fields[0]?.fieldtype !== "Tab Break") tab_labels.unshift(__("Details"));

	const sections = [];
	let section = null;
	let section_ok = true;
	let column = null;
	// The form gives a trailing table a smaller margin (form.scss), but only when nothing
	// follows it in the DOM, hidden fields included. So the mark goes on when the last field
	// of the column in the meta is a table we drew.
	let column_ends_on_drawn_field = false;
	let in_first_tab = true;

	const close_column = () => {
		if (column?.length && column_ends_on_drawn_field) {
			column[column.length - 1] = column[column.length - 1].replace(
				'class="skeleton-field"',
				'class="skeleton-field is-last"'
			);
		}
		column = null;
		column_ends_on_drawn_field = false;
	};
	const open_section = (df) => {
		close_column();
		section_ok = !df?.depends_on;
		section = {
			heading: Boolean(df?.label),
			label: df?.label,
			hide_border: cint(df?.hide_border),
			columns: [],
		};
		if (section_ok) sections.push(section);
	};
	const open_column = () => {
		close_column();
		if (!section) open_section();
		column = [];
		section.columns.push(column);
	};

	for (const df of meta.fields) {
		if (df.fieldtype === "Tab Break") {
			if (!in_first_tab || sections.length) break;
			in_first_tab = false;
			continue;
		}
		if (df.fieldtype === "Section Break") {
			open_section(df);
			continue;
		}
		if (!section_ok) continue;
		if (df.fieldtype === "Column Break") {
			open_column();
			continue;
		}
		if (skip(df)) {
			column_ends_on_drawn_field = false;
			continue;
		}
		if (!column) open_column();
		column.push(skeleton_field(df));
		column_ends_on_drawn_field = df.fieldtype === "Table";
	}
	close_column();

	const tabs =
		tab_labels.length > 1
			? `<div class="skeleton-tabs">${tab_labels
					.slice(0, 5)
					.map(
						(label, i) =>
							`<span class="${i ? "" : "active"}">${text_or_bar(
								label,
								"60px"
							)}</span>`
					)
					.join("")}</div>`
			: "";

	const body = sections
		.filter((s) => s.columns.some((c) => c.length))
		.map((s) => {
			const heading = s.heading
				? `<div class="skeleton-heading">${text_or_bar(s.label, "25%")}</div>`
				: "";
			const columns = s.columns.map(
				(c) => `<div class="flex-1 min-w-0">${c.join("")}</div>`
			);
			const classes = [
				"skeleton-section",
				s.heading && "has-heading",
				s.hide_border && "hide-border",
			]
				.filter(Boolean)
				.join(" ");
			return `<div class="${classes}">
				${heading}<div class="skeleton-columns">${columns.join("")}</div>
			</div>`;
		})
		.join("");

	return tabs + body;
}

frappe.ui.SidePanel = class SidePanel {
	constructor() {
		// One Layout per doctype; refresh(doc) repoints it at a different document.
		this.layouts = {};
		// Previews fetched while the panel is open, so back and revisits are instant.
		this.previews = {};
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
		this.make_buttons();

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

	make_buttons() {
		const ghost = (opts) => frappe.ui.button({ variant: "ghost", ...opts });

		ghost({
			icon: "arrow-left",
			tooltip: __("Back"),
			css_class: "side-panel-back hidden",
			onclick: () => this.back(),
		}).prependTo(this.$panel.find(".side-panel-header"));

		const $actions = this.$panel.find(".side-panel-actions");
		ghost({
			icon: "arrow-up-right",
			tooltip: __("Open in full page"),
			onclick: () => {
				const current = this.current;
				this.close();
				if (current) frappe.set_route("Form", current.doctype, current.docname);
			},
		}).appendTo($actions);
		ghost({ icon: "x", tooltip: __("Close"), onclick: () => this.close() }).appendTo($actions);
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

		const cached = this.previews[`${doctype}/${docname}`];
		if (cached) {
			this.show_preview(doctype, docname, cached);
			return;
		}

		this.set_header(doctype, docname, null);
		const had_meta = Boolean(frappe.get_meta(doctype));
		this.set_state("loading");

		// The meta comes from the framework cache (one fetch per doctype per session); only the
		// document is fetched every time. A doctype seen for the first time gets its skeleton
		// redrawn once the meta is in.
		const meta_ready = frappe.model.with_doctype(doctype).then(() => {
			if (!had_meta && token === this.token) this.set_state("loading");
		});
		const timeout = new Promise((_, reject) => setTimeout(reject, LOAD_TIMEOUT_MS));

		const load = frappe
			.call({
				method: "frappe.desk.doc_preview.get_preview",
				type: "GET",
				args: { doctype, name: docname },
			})
			.then((r) => r?.message);

		// Building the form is heavy; doing it mid-slide stalls the animation.
		Promise.all([meta_ready, Promise.race([load, timeout]), this.slide_done])
			.then(([, preview]) => {
				if (token !== this.token) return;
				if (!preview?.doc) throw new Error("not loaded");

				this.previews[`${doctype}/${docname}`] = preview;
				this.show_preview(doctype, docname, preview);
			})
			.catch((e) => {
				if (token !== this.token) return;
				console.error("[side panel] failed to render", doctype, docname, e);
				this.set_state("error");
			});
	}

	show_preview(doctype, docname, preview) {
		this.preview = preview;
		this.render_doc(doctype, preview);
		this.set_header(doctype, docname, preview);
		this.set_state("ready");
	}

	render_doc(doctype, preview) {
		const doc = preview.doc;
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
			// Override on the controls (persists across refresh); grids stay read-only via
			// static_rows (prepare_grids).
			force_read_only(layout.fields_list);
			entry = this.layouts[doctype] = { layout, $wrapper };
		}

		this.$body.find(".side-panel-doc").addClass("hidden");
		entry.$wrapper.removeClass("hidden");

		// Read by read_only_status(), so permlevel-restricted fields stay hidden.
		entry.layout.side_panel_permlevels = (preview.permlevels || []).map(cint);
		entry.layout.doc = doc;
		this.prepare_grids(entry.layout, doc);
		entry.layout.refresh(doc);
		// refresh() rebuilds grid_rows, so the rows to bind only exist now.
		this.make_rows_openable(entry.layout);
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

		const parent_doc = this.preview?.doc;

		const dialog = new frappe.ui.Dialog({
			title: __("Row #{0}", [row_doc.idx]),
			size: "large",
		});
		this.row_dialog = dialog;
		dialog.$wrapper.addClass("side-panel-row-dialog");

		// Read-only: no action to offer.
		dialog.get_primary_btn().hide();

		render_static_doc_fields(dialog.body, child_doctype, row_doc, parent_doc, this.preview);

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

	set_header(doctype, docname, preview) {
		this.$panel.find(".side-panel-doctype").text(__(doctype));
		this.$panel.find(".side-panel-title").text(docname);

		const $indicator = this.$panel.find(".side-panel-indicator").empty();
		const indicator = preview ? frappe.get_indicator(preview.doc, doctype) : null;
		if (indicator) {
			const theme = indicator[1] === "black" ? "gray" : indicator[1]; // no black badge theme
			frappe.ui.badge({ label: indicator[0], theme }).appendTo($indicator);
		}
	}

	// The skeleton is an overlay: the form renders underneath, then the skeleton fades out,
	// so nothing in the body moves when the document lands.
	set_state(state) {
		const $skeleton = this.$body.find(".side-panel-skeleton");
		this.$body.find(".side-panel-message").remove();
		this.$body.find(".side-panel-doc").toggleClass("is-ready", state === "ready");

		if (state === "loading") {
			$skeleton.remove();
			$('<div class="side-panel-skeleton"></div>')
				.html(skeleton_form(frappe.get_meta(this.current?.doctype)))
				.appendTo(this.$body);
		} else if (state === "ready") {
			$skeleton.addClass("is-done");
			setTimeout(() => $skeleton.remove(), 200);
		} else if (state === "error") {
			$skeleton.remove();
			$('<div class="side-panel-message text-center text-extra-muted"></div>')
				.text(__("Could not load this document"))
				.prependTo(this.$body);
		}
	}

	show() {
		this.$panel.removeClass("hidden");
		this.$panel[0].offsetWidth; // commit the closed position so the slide starts from it
		this.$panel.addClass("is-open");
		$("body").addClass("side-panel-open");
		this.slide_done = this.after_slide();
	}

	after_slide() {
		return new Promise((resolve) => {
			const done = (e) => {
				if (e && e.target !== this.$panel[0]) return;
				this.$panel.off("transitionend.side-panel");
				resolve();
			};
			this.$panel.on("transitionend.side-panel", done);
			setTimeout(done, 300); // in case the transition never fires
		});
	}

	is_open() {
		return this.$panel.hasClass("is-open");
	}

	close() {
		if (!this.is_open()) return;
		this.token++; // abandon any in-flight render
		this.$panel.removeClass("is-open");
		this.after_slide().then(() => {
			if (!this.is_open()) this.$panel.addClass("hidden");
		});
		$("body").removeClass("side-panel-open");
		this.history = [];
		this.current = null;
		this.previews = {};
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
