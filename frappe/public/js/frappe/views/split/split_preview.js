frappe.provide("frappe.views");

const MAX_PREVIEW_FIELDS = 12;
const LONG_TEXT_FIELDTYPES = [
	"Small Text",
	"Text",
	"Long Text",
	"Text Editor",
	"Markdown Editor",
	"HTML Editor",
];

/**
 * The split view's detail when the DocType draws none: a header with the title, badge and
 * actions, the record's main values as label and value pairs, its long texts below them, and a
 * bar to step through the list. The full form is a click away, so this stays short.
 */
frappe.views.SplitViewPreview = class SplitViewPreview {
	constructor({ view, name, $parent }) {
		this.view = view;
		this.name = name;
		this.make($parent);
		this.update_position();
		this.set_header(view.data.find((doc) => doc.name === name) || { name });
		view.detail_loader.show(name, {
			empty: () => this.$body.empty(),
			skeleton: () => this.$body.html(this.get_skeleton()),
			render: (preview) => {
				this.set_header(preview.doc);
				this.render_fields(preview);
			},
			error: () =>
				this.$body.html(
					frappe.ui.empty_state.html({ title: __("Could not load this record") })
				),
		});
	}

	make($parent) {
		this.$panel = $(`<div class="split-view-preview">
			<div class="split-view-preview-scroll">
				<div class="split-view-preview-content">
					<div class="split-view-preview-head">
						<div class="split-view-preview-heading">
							<div class="split-view-preview-title-line">
								<h2 class="split-view-preview-title text-p-lg-semibold"></h2>
								<span class="split-view-preview-badge"></span>
							</div>
							<p class="split-view-preview-subtitle text-p-base"></p>
						</div>
						<div class="split-view-preview-actions"></div>
					</div>
					<div class="split-view-preview-body"></div>
				</div>
			</div>
			<div class="split-view-preview-bar"></div>
		</div>`).appendTo($parent);
		this.view.make_back_button().prependTo(this.$panel.find(".split-view-preview-head"));
		this.$position_bar = this.$panel.find(".split-view-preview-bar");
		this.$body = this.$panel.find(".split-view-preview-body");
		this.make_actions(this.$panel.find(".split-view-preview-actions"));
	}

	make_actions($actions) {
		frappe.ui
			.button({
				label: __("Open"),
				icon_right: "arrow-up-right",
				variant: "subtle",
				onclick: () => this.view.open_form(this.name),
			})
			.appendTo($actions);
	}

	set_header(doc) {
		this.title = this.view.get_title(doc);
		this.$panel.find(".split-view-preview-title").text(this.title);
		const indicator = this.view.get_indicator(doc);
		this.$panel
			.find(".split-view-preview-badge")
			.html(indicator ? frappe.ui.badge.html(indicator) : "");
		const row = this.view.data.find((row) => row.name === this.name) || doc;
		this.subtitle = cstr(this.view.get_item(row).subtitle).split(" · ")[0];
		this.$panel.find(".split-view-preview-subtitle").text(this.subtitle);
	}

	refresh() {
		return this.view.detail_loader.refresh();
	}

	destroy() {
		this.view.detail_loader.cancel();
	}

	/** Up and down through the list, and where the open record is in it, e.g. "2 of 14". */
	update_position() {
		const view = this.view;
		const { index, total, is_estimate } = view.get_position(this.name);
		const $bar = this.$position_bar;
		$bar.find("*").each((_, node) => $(node).data("es-tooltip")?.destroy());
		$bar.empty().append(
			frappe.ui.button({
				icon: "chevron-up",
				variant: "ghost",
				tooltip: __("Previous (k)"),
				disabled: index <= 1,
				onclick: () => view.select_next(-1),
			}),
			frappe.ui.button({
				icon: "chevron-down",
				variant: "ghost",
				tooltip: __("Next (j)"),
				disabled: !view.data.length || (index > 0 && index >= total && !view.has_more()),
				onclick: () => view.select_next(1),
			}),
			index
				? $('<span class="split-view-position text-p-sm"></span>').text(
						__("{0} of {1}", [
							format_number(index, null, 0),
							`${format_number(total, null, 0)}${is_estimate ? "+" : ""}`,
						])
				  )
				: null
		);
	}

	get_skeleton() {
		const facts = Array.from(
			{ length: 6 },
			() =>
				`<dt>${frappe.ui.skeleton.html({ width: "88px", height: "12px" })}</dt>
				<dd>${frappe.ui.skeleton.html({ width: "60%", height: "12px" })}</dd>`
		).join("");
		return `<dl class="split-view-fields text-base" aria-hidden="true">${facts}</dl>`;
	}

	render_fields({ doc, permlevels }) {
		const fields = this.get_fields(doc, (permlevels || []).map(cint));
		if (!fields.length) {
			this.$body.html(
				`<p class="text-p-sm text-ink-gray-5">${__("No other details to show.")}</p>`
			);
			return;
		}
		const short = fields.filter((df) => !LONG_TEXT_FIELDTYPES.includes(df.fieldtype));
		const long = fields.filter((df) => LONG_TEXT_FIELDTYPES.includes(df.fieldtype));
		this.$body.empty();
		if (short.length) this.$body.append(this.make_field_list(short, doc));
		for (const df of long) {
			this.$body.append(this.make_text_section(df, doc));
		}
		this.limit_text_sections();
	}

	make_field_list(fields, doc) {
		const list = document.createElement("dl");
		list.className = "split-view-fields text-base";
		for (const df of fields) {
			const label = document.createElement("dt");
			label.className = "text-p-base";
			label.textContent = this.get_label(df);
			const value = document.createElement("dd");
			this.render_value(value, df, doc);
			value.title = value.textContent;
			list.append(label, value);
		}
		return list;
	}

	get_label(df) {
		return __(df.label || df.fieldname, null, this.view.doctype);
	}

	// A long text under its own heading, folded to a few lines with a toggle when it runs longer.
	make_text_section(df, doc) {
		const $section = $(`<section class="split-view-section">
			<h3 class="split-view-section-heading text-base-medium"></h3>
			<div class="split-view-section-text text-p-base"></div>
		</section>`);
		$section.find(".split-view-section-heading").text(this.get_label(df));
		const text = $section.find(".split-view-section-text")[0];
		if (["Text Editor", "Markdown Editor"].includes(df.fieldtype)) {
			text.innerHTML = this.view.format_value(df, doc);
		} else {
			text.textContent = cstr(doc[df.fieldname]);
			text.classList.add("split-view-field-text");
		}
		const $toggle = frappe.ui
			.button({
				label: __("Show more"),
				variant: "ghost",
				size: "sm",
				onclick: () => {
					const is_open = text.toggleAttribute("data-expanded");
					$toggle
						.find(".es-button__label")
						.text(is_open ? __("Show less") : __("Show more"));
				},
			})
			.addClass("split-view-section-toggle")
			.hide();
		return $section.append($toggle);
	}

	limit_text_sections() {
		this.$body.find(".split-view-section").each((_, section) => {
			const text = section.querySelector(".split-view-section-text");
			if (text.scrollHeight > text.clientHeight + 1) {
				$(section).find(".split-view-section-toggle").show();
			}
		});
	}

	// In-preview fields when the DocType marks any, else the ones the list and its filters show.
	get_fields(doc, permlevels) {
		const title_field = this.view.meta.title_field;
		const badge = this.view.get_indicator(doc)?.label;
		const fields = this.view.meta.fields.filter((df) =>
			this.has_value_to_show(df, doc, { permlevels, badge })
		);
		const in_preview = fields.filter((df) => df.in_preview);
		const shown = in_preview.length
			? in_preview
			: fields.filter(
					(df) =>
						df.in_list_view ||
						df.bold ||
						df.in_standard_filter ||
						df.fieldname === title_field
			  );
		return shown.slice(0, MAX_PREVIEW_FIELDS);
	}

	has_value_to_show(df, doc, { permlevels, badge }) {
		if (!frappe.model.is_value_type(df.fieldtype) || df.hidden) return false;
		if (!permlevels.includes(cint(df.permlevel))) return false;
		const is_long = LONG_TEXT_FIELDTYPES.includes(df.fieldtype);
		if (df.fieldname === this.view.meta.title_field && !is_long) return false;
		const value = doc[df.fieldname];
		if (df.fieldtype === "Select" && value && __(value) === badge) return false;
		if (df.fieldtype === "Check") return Boolean(cint(value));
		if (df.fieldtype === "Rating") return flt(value) > 0;
		if (value == null || value === "") return false;
		const text = this.view.get_plain_text(this.view.format_value(df, doc));
		return ![this.title, this.subtitle].includes(text);
	}

	render_value(el, df, doc) {
		const value = doc[df.fieldname];
		if (df.fieldtype === "Link" || df.fieldtype === "Dynamic Link") {
			this.render_link(el, df.fieldtype === "Link" ? df.options : doc[df.options], value);
		} else if (df.fieldtype === "Check") {
			el.textContent = __("Yes");
		} else if (df.fieldtype === "Rating") {
			el.innerHTML = this.view.format_value(df, doc);
		} else {
			el.textContent = this.view.get_plain_text(this.view.format_value(df, doc));
		}
	}

	render_link(el, doctype, value) {
		const title = (doctype && frappe.utils.get_link_title(doctype, value)) || value;
		if (!doctype || !frappe.model.can_read(doctype)) {
			el.textContent = title;
			return;
		}
		const link = document.createElement("a");
		link.href = `/desk/${frappe.router.slug(doctype)}/${encodeURIComponent(value)}`;
		link.textContent = title;
		el.append(link);
	}
};
