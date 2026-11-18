import { GROUP_BY_KEYS, is_scan_helper, std_field } from "../ui/components/filter_utils.js";

frappe.provide("frappe.views");

/**
 * A list's quick filter chips and its Filter panel, kept in step with the list's filter rows.
 * Loaded with the filter_chips bundle, only where the chips are switched on; `area` is the list's
 * FilterArea, which keeps the rows, the Filter button and `area.filter_chips`.
 */
frappe.views.ListFilterChips = class ListFilterChips {
	constructor(area) {
		this.area = area;
		this.list_view = area.list_view;
		this.pending = 0;
		this.queue = Promise.resolve();
		// rows can pass through an empty step (cleared, then set from a link); follow once they settle
		this.sync = frappe.utils.debounce(() => this.sync_now(), 80);
	}

	async make() {
		const { area, list_view } = this;
		const { doctype, meta, settings, view_name } = list_view;
		const configs = list_view.custom_filter_configs || settings.custom_filter_configs;
		const custom = configs ? await (typeof configs === "function" ? configs() : configs) : [];
		const group_by_fields = frappe.get_user_settings(doctype)?.group_by_fields || [];
		// a DocField's own `doctype` is "DocField"; the chips need the one it belongs to
		const fields = meta.fields
			.filter(
				(df) =>
					(df.fieldname === meta.title_field ||
						((df.in_standard_filter || group_by_fields.includes(df.fieldname)) &&
							frappe.model.is_value_type(df.fieldtype))) &&
					!is_scan_helper(df) &&
					frappe.perm.has_perm(doctype, df.permlevel)
			)
			.map((df) => ({ ...df, doctype }));
		fields.unshift(...custom.map((df) => ({ ...df, doctype: df.doctype || doctype })));
		fields.sort((a, b) => (a.fieldtype === "Check") - (b.fieldtype === "Check"));
		if (!settings.hide_name_filter) {
			fields.unshift({
				fieldname: "name",
				label: "ID",
				fieldtype: "Data",
				icon: "search",
				doctype,
			});
		}
		// "Customize Quick Filters" can also pick these, which aren't the DocType's own fields
		for (const [key, fieldname] of Object.entries(GROUP_BY_KEYS)) {
			if (!group_by_fields.includes(key)) continue;
			const df = std_field(doctype, fieldname);
			fields.push({ ...df, doctype, counts: true });
		}

		const start = (list_view.filters = list_view.filters || []);
		for (const df of custom) {
			if (df.default == null || df.default === "") continue;
			if (start.some((f) => f[1] === df.fieldname)) continue;
			start.push([df.doctype || doctype, df.fieldname, df.condition || "=", df.default]);
		}

		const conditions = frappe.get_user_settings(doctype, view_name)?.filter_conditions || {};
		// a link's filters when it has some (a page load leaves an empty route_options)
		// the list's own parser: a Report view's also sets its group-by, which isn't made yet
		const from_link =
			frappe.route_options &&
			frappe.views.ListView.prototype.parse_filters_from_route_options.call(list_view);
		const chips = (area.filter_chips = new frappe.ui.FilterChips({
			doctype,
			filters: from_link?.length ? from_link : start.filter((f) => f.length >= 4),
			fields: fields.map((df) => ({ ...df, label: __(df.label, null, df.parent) })),
			conditions,
			on_condition: (key, condition) => {
				conditions[key] = condition;
				list_view.save_view_user_settings?.({ filter_conditions: { ...conditions } });
			},
			onchange: (filters) => this.set_rows(filters),
			on_advanced: (doctype, fieldname) =>
				this.open_panel({ view: "advanced", focus: { doctype, fieldname } }),
			onopen: () => this.close_on_route_change(),
		}));
		// list scripts reach a quick filter at page.fields_dict.<fieldname>
		for (const df of fields.filter((df) => df.doctype === doctype)) {
			list_view.page.fields_dict[df.fieldname] = chips.box_of(doctype, df.fieldname);
		}
		area.standard_filters_wrapper = list_view.page.page_form.find(".standard-filter-section");
		area.standard_filters_wrapper.append(chips.$wrapper);
		// the page shows its form row once a field is added; the chips add none
		list_view.page.show_form();
		this.hold_toolbar();
		// the rows fill the room the toolbar leaves: chips taking more rows or fewer change it
		const fit = frappe.utils.debounce(() => {
			if (list_view.$result?.is(":visible")) list_view.set_result_height?.();
		}, 100);
		new ResizeObserver(fit).observe(list_view.page.page_form[0]);
	}

	// nothing under the pointer moves; held widths settle once it leaves the toolbar
	hold_toolbar() {
		const $form = this.list_view.page.page_form;
		// the desk's padding for a count and × waits too, or the two would add up
		const parts = () => {
			const button = this.area.filter_button?.[0];
			return button ? [button, button.parentElement] : [];
		};
		$form.on("pointerenter", (e) => {
			if (e.pointerType === "touch") return;
			this.area.filter_chips.hold_widths(true);
			for (const el of parts()) el.style.minWidth = `${el.getBoundingClientRect().width}px`;
			// only a × showing now can go while held
			if (this.area.filter_x_button?.is(":visible")) {
				this.area.filter_button.closest(".filter-selector").attr("data-held", "");
			}
		});
		$form.on("pointerleave", () => {
			this.area.filter_chips.hold_widths(false);
			for (const el of parts()) el.style.minWidth = "";
			this.area.filter_button?.closest(".filter-selector").removeAttr("data-held");
		});
	}

	/** The rows take the chips' filters; one rebuild at a time, in order. */
	set_rows(filters) {
		this.pending++;
		const rebuild = () => {
			const group = this.area.filter_list;
			group.filters.forEach((f) => f.remove());
			group.filters = [];
			group.filter_order = [];
			return group.add_filters(filters);
		};
		// a step that failed doesn't stop the ones after it, nor keep the chips from syncing
		this.queue = this.queue.then(rebuild, rebuild).finally(() => {
			this.pending--;
			this.area.debounced_refresh_list_view();
		});
		return this.queue;
	}

	/** The chips take the rows' filters; rows being rebuilt from the chips keep the chips' own. */
	sync_now() {
		if (this.pending) return;
		this.area.filter_chips?.set_filters(this.area.filter_list.get_filters());
	}

	open_panel({ view, focus } = {}) {
		const button = this.area.filter_button;
		if (!this.popover) {
			this.popover = new frappe.ui.Popover({
				trigger: button,
				// the panel ends where the Filter button's group does, its × included
				anchor: button.parent(),
				content: () => this.make_panel(),
				side: "bottom",
				align: "end",
				css_class: "es-filter-panel-popover",
				on_open: () => this.close_on_route_change(),
				on_close: () => {
					this.panel?.destroy();
					this.panel = null;
					this.remember_panel_field();
				},
			});
			// the button's own click handler decides which panel opens
			this.popover.trigger_el.removeEventListener("click", this.popover.ontriggerclick);
		}
		this.view = { view, focus };
		this.popover.close("owner");
		this.popover.open();
	}

	toggle_panel() {
		if (this.popover?.is_open) this.popover.close("owner");
		else this.open_panel();
	}

	// the field picked last in the panel opens next time; saved once, as the panel closes
	remember_panel_field() {
		if (!this.picked) return;
		const { doctype, fieldname } = this.picked;
		this.picked = null;
		frappe.model.user_settings.save(this.list_view.doctype, "filter_panel_field", {
			doctype,
			fieldname,
		});
	}

	// a page change closes the panel and a chip's picker; one listener waits at a time, and
	// `once`, as the router's `off` can't unbind
	close_on_route_change() {
		if (this.route_listener) return;
		this.route_listener = true;
		frappe.router.once("change", () => {
			this.route_listener = false;
			this.popover?.close();
			this.area.filter_chips?.close();
		});
	}

	make_panel() {
		const group = this.area.filter_list;
		if (!this.sections)
			this.sections = frappe.ui.FilterPanel.sections_for(this.list_view.doctype);
		this.panel = new frappe.ui.FilterPanel({
			chips: this.area.filter_chips,
			sections: this.sections,
			...this.view,
			last_used: frappe.get_user_settings(this.list_view.doctype).filter_panel_field,
			on_pick: (df) => (this.picked = df),
			advanced: {
				element: () => {
					group.applied_filters = JSON.stringify(group.get_filters());
					return group.get_popover_content();
				},
				// as the rows' own popover does on close: drop half-filled rows, apply the rest
				on_hide: () => {
					group.update_filters();
					group.apply_changes();
					// the panel redraws its picker from the chips next
					this.sync.cancel();
					this.sync_now();
				},
			},
		});
		return this.panel.$wrapper[0];
	}
};
