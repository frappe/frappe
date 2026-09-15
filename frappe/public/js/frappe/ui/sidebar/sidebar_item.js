frappe.provide("frappe.ui.sidebar_item");

// Resolve a sidebar item (from `bootinfo.module_sidebars`) to a navigable route.
// Shared by the rendered sidebar links and the header workspace switcher.
frappe.ui.sidebar_item.get_route = function (item, edit_mode = false) {
	let path;
	if (item.type !== "Link") return path;

	if (item.link_type === "Report") {
		let args = {
			type: item.link_type,
			name: item.link_to,
		};
		if (!edit_mode) {
			if (item.report) {
				args.is_query_report =
					item.report.report_type === "Query Report" ||
					item.report.report_type == "Script Report";
				args.report_ref_doctype = item.report.ref_doctype;
			} else {
				return;
			}
		}

		path = frappe.utils.generate_route(args);
	} else if (item.link_type == "Workspace") {
		let workspaces = frappe.workspaces[frappe.router.slug(item.link_to)];
		if (workspaces && workspaces.public) {
			path = "/desk/" + frappe.router.slug(item.link_to);
		} else {
			path = "/desk/private/" + frappe.router.slug(item.link_to);
		}

		if (item.route) {
			path = item.route;
		}
	} else if (item.link_type === "URL") {
		path = item.url;
	} else if (item.link_type == "Page" && item.route_options) {
		path = frappe.utils.generate_route({
			type: item.link_type,
			name: item.link_to,
			route_options: JSON.parse(item.route_options),
		});
	} else {
		let args = {
			type: item.link_type,
			name: item.link_to,
			tab: item.tab,
		};
		// get_filter_as_json() returns null for an empty filter array, so an item stored
		// with `filters` of "[]" lands here with nothing to convert.
		const filters_as_json = item.filters
			? frappe.utils.get_filter_as_json(JSON.parse(item.filters))
			: null;
		if (filters_as_json) {
			let filters_json = JSON.parse(filters_as_json);
			for (const [key, value] of Object.entries(filters_json)) {
				if (Array.isArray(value)) {
					filters_json[key] = value[0] === "=" ? value[1] : JSON.stringify(value);
				}
			}
			if (item.link_type == "DocType") {
				args.doc_view = "List";
				args.route_options = filters_json;
			}
		} else if (item.route_options && item.link_type == "DocType") {
			args.doc_view = "List";
			args.route_options = JSON.parse(item.route_options);
		}
		path = frappe.utils.generate_route(args);

		// If a DocType Layout is specified on this link, append ?layout=<route>
		// so the form/list opens under that layout context.
		if (item.link_type === "DocType" && item.doctype_layout) {
			const layout_info = (frappe.boot.doctype_layouts || []).find(
				(l) => l.name === item.doctype_layout
			);
			if (layout_info) {
				const doctype_slug = frappe.router.slug(item.link_to);
				path = `/app/${doctype_slug}?layout=${encodeURIComponent(layout_info.name)}`;
			}
		}
	}

	return path;
};

frappe.ui.sidebar_item.TypeLink = class SidebarItem {
	constructor(opts) {
		this.item = opts.item;
		this.container = opts.container;
		this.nested_items = opts.item.nested_items || [];
		// The module whose sidebar this item is in, read off the sidebar rather than out of the
		// DOM. It keys the collapsed/expanded state of section breaks in localStorage.
		//
		// It used to read `data-title` and lowercase it, falling back to `sidebar.sidebar_title`,
		// a property that no longer exists, so the fallback was always undefined and every module
		// shared one state. The lowercasing also made it a fourth keyspace, in a change whose
		// point was to have one: the exact-case module name.
		this.current_module = frappe.app.sidebar.current_module;
		this.prepare(opts);
		this.make();
	}
	get_path() {
		return frappe.ui.sidebar_item.get_route(this.item);
	}

	prepare() {}
	make() {
		this.path = this.get_path();
		if (!this.path && !this.item.standard && this.item.type != "Section Break") {
			return;
		}
		this.set_suffix();
		// `parent` is only set on items find_nested_items() actually nested; a row can carry
		// `child` without one (a Section Break, or a child with no section above it).
		if (!this.item.icon && !(this.item.child && this.item.parent?.indent)) {
			this.item.icon = "list";
		}
		this.wrapper = $(
			frappe.render_template("sidebar_item", {
				item: this.item,
				path: this.path,
			})
		);
		$(this.container).append(this.wrapper);
		this.setup_click();
	}

	setup_click() {
		if (!this.path) return;
		this.wrapper.find(".item-anchor").on("click", () => {
			if (frappe.is_mobile()) {
				frappe.app.sidebar.close();
			}
		});
	}
	set_suffix() {
		if (this.item.suffix) {
			if (this.item.suffix.keyboard_shortcut) {
				this.item.suffix = this.get_shortcut_html(this.item.suffix.keyboard_shortcut);
			}
		}
	}
	get_shortcut_html(shortcut) {
		shortcut = frappe.ui.keys.get_shortcut_label(shortcut);
		return `<span class="keyboard-shortcut">${shortcut}</span>`;
	}
};

frappe.ui.sidebar_item.TypeSectionBreak = class SectionBreakSidebarItem extends (
	frappe.ui.sidebar_item.TypeLink
) {
	prepare(opts) {
		this.collapsed = false;
		this.nested_items = opts.item.nested_items || this.nested_items;
		this.items = [];
		this.$items = [];
		const storedState = localStorage.getItem("section-breaks-state");
		this.section_breaks_state = storedState ? JSON.parse(storedState) : {};
	}
	add_items() {
		this.$item_control = this.wrapper.find(".sidebar-item-control");
		this.$nested_items = this.wrapper.find(".nested-container").first();
		this.nested_items.forEach((f) => {
			this.items.push(
				frappe.app.sidebar.make_sidebar_item({
					container: this.$nested_items,
					item: f,
				})
			);
		});
		this.full_template = $(this.wrapper);
	}
	make() {
		if (this.nested_items.length == 0) {
			return;
		}
		super.make();
		if (!this.item.nested_items || this.item.nested_items.length == 0) return;
		this.add_items();
		$(this.container).append(this.full_template);
		this.toggle_on_collapse();
		this.enable_collapsible(this.item, this.full_template);
	}
	open() {
		this.collapsed = false;
		this.toggle();
	}
	close() {
		this.collapsed = true;
		this.toggle();
	}
	toggle() {
		if (this.collapsed) {
			this.$drop_icon
				.attr("data-state", "closed")
				.find("use")
				.attr("href", "#icon-chevron-right");
			$(this.$nested_items).addClass("hidden");
		} else {
			this.$drop_icon
				.attr("data-state", "opened")
				.find("use")
				.attr("href", "#icon-chevron-down");
			$(this.$nested_items).removeClass("hidden");
		}
	}
	toggle_on_collapse() {
		const me = this;
		this.old_state;
		$(document).on("sidebar-expand", function (event, expand) {
			if (expand.sidebar_expand) {
				$(me.wrapper.find(".section-break")).removeClass("hidden");
				$(me.wrapper.find(".divider")).addClass("hidden");
				if (me.old_state) {
					me.collapsed = me.old_state;
					me.toggle();
				}
			} else {
				$(me.wrapper.find(".section-break")).addClass("hidden");
				$(me.wrapper.find(".divider")).removeClass("hidden");
				me.old_state = me.collapsed;
				me.open();
				if (me.item.indent) {
					me.close();
				}
			}
		});
	}

	enable_collapsible(item, $item_container) {
		let sidebar_control = this.$item_control;
		let stroke_color = window.getComputedStyle(document.body).getPropertyValue("--ink-gray-5");

		if (item.collapsible) {
			this.$drop_icon = $(`<button class="btn-reset drop-icon hidden">`)
				.html(frappe.utils.icon("chevron-down", "sm", "", "", "", "", stroke_color))
				.appendTo(sidebar_control);

			this.$drop_icon.removeClass("hidden");
		} else if (item.show_arrow) {
			// The leading chevron span was removed from sidebar_item.html, so build the
			// toggle indicator here instead of selecting the now-absent [item-icon] span.
			this.$drop_icon = $(`<button class="btn-reset drop-icon">`)
				.html(frappe.utils.icon("chevron-right", "sm", "", "", "", "", stroke_color))
				.prependTo(this.wrapper.find(".item-anchor").first());
		}

		if (item.keep_closed) {
			this.close();
		}
		if (
			Object.keys(this.section_breaks_state) &&
			this.section_breaks_state[this.current_module]
		) {
			this.apply_section_break_state();
		}
		if (item.collapsible || item.show_arrow) {
			this.setup_event_listner();
		}
	}
	apply_section_break_state() {
		const me = this;
		let current_sidebar_state = this.section_breaks_state[this.current_module];
		for (const [element_name, collapsed] of Object.entries(current_sidebar_state)) {
			if (this.item.label == element_name) {
				me.collapsed = collapsed;
				me.toggle();
			}
		}
	}
	setup_event_listner() {
		const me = this;

		$(this.wrapper.find(".standard-sidebar-item")[0]).on("click", (e) => {
			me.collapsed = me.$drop_icon.find("use").attr("href") === "#icon-chevron-down";
			me.toggle();

			if (e.originalEvent.isTrusted) {
				me.save_section_break_state();
			}
			// Docking the sidebar is how a collapsed one shows the group that was just
			// expanded, since the group itself is off screen while collapsed.
			if (!frappe.app.sidebar.sidebar_expanded) {
				frappe.app.sidebar.open();
				this.open();
			}
		});
	}
	save_section_break_state() {
		if (!this.section_breaks_state[this.current_module]) {
			this.section_breaks_state[this.current_module] = {};
		}

		this.section_breaks_state[this.current_module][this.item.label] = this.collapsed;

		localStorage.setItem("section-breaks-state", JSON.stringify(this.section_breaks_state));
	}
};

frappe.ui.sidebar_item.TypeButton = class SidebarButton extends frappe.ui.sidebar_item.TypeLink {
	constructor(item) {
		super(item);
		this.item.id && this.wrapper.attr("id", this.item.id);
		this.item.class && this.wrapper.attr("class", this.item.class);
	}

	// overrides TypeLink.setup_click(), invoked once via the base class's make()
	setup_click() {
		const me = this;
		if (this.item.onClick) {
			this.wrapper.on("click", function () {
				me.item.onClick && me.item.onClick();
			});
		}
	}
};
