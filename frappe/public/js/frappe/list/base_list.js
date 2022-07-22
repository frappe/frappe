frappe.provide("frappe.views");

frappe.views.BaseList = class BaseList {
	constructor(opts) {
		Object.assign(this, opts);
	}

	show() {
		return frappe.run_serially([
			() => this.show_skeleton(),
			() => this.fetch_meta(),
			() => this.hide_skeleton(),
			() => this.check_permissions(),
			() => this.init(),
			() => this.before_refresh(),
			() => this.refresh(),
		]);
	}

	teardown() {

	}

	init() {
		let tasks = [
			this.setup_defaults,
			this.set_stats,
			this.setup_fields,
			// make view
			this.setup_page,
			this.setup_side_bar,
			this.setup_main_section,
			this.setup_view,
			this.setup_view_menu,
		].map((fn) => fn.bind(this));

		return frappe.run_serially(tasks);
	}

	setup_defaults() {
		this.page_name = frappe.get_route_str();
		this.page_title = this.page_title || frappe.router.doctype_layout || __(this.doctype);
		this.meta = frappe.get_meta(this.doctype);
		this.settings = this.get_settings();
		if (this.settings.init) {
			this.settings.init();
		}

		this.data = [];
		this.method = "frappe.desk.reportview.get";
		this.can_create = frappe.model.can_create(this.doctype);
		this.can_write = frappe.model.can_write(this.doctype);

		const filter_arg = (k, v) => v !== undefined

		Object.assign(this, {
			// Priority 4: coded defaults
			...frappe.utils.filter_object(this.get_default_args(), filter_arg),
			// Priority 3: view settings (configured per doctype)
			...frappe.utils.filter_object(this.get_settings_args(), filter_arg),
			// Priority 2: active presets (e.g. a saved report, or kanban board)
			...frappe.utils.filter_object(this.get_presets_args(), filter_arg),
			// Priority 1: route options (current window state)
			...frappe.utils.filter_object(this.get_route_options_args(), filter_arg)
		});

		// Setup buttons
		this.primary_action = null;
		this.secondary_action = null;

		this.menu_items = [
			{
				label: __("Refresh"),
				action: () => this.refresh(),
				class: "visible-xs",
			},
		];
	}

	get_settings() {
		return frappe.listview_settings[this.doctype] || {};
	}

	get_route_options_args() {
		const filters = frappe.route_options.filters ? Object.entries(frappe.route_options.filters).reduce((acc, [field, value]) => {
			let doctype = null;

			// if `Child DocType.fieldname`
			if (field.includes(".")) {
				doctype = field.split(".")[0];
				field = field.split(".")[1];
			}

			// find the table in which the key exists
			// for example the filter could be {"item_code": "X"}
			// where item_code is in the child table.

			// we can search all tables for mapping the doctype
			if (!doctype) {
				doctype = frappe.meta.get_doctype_for_field(
					this.doctype,
					field
				);
			}

			if (doctype) {
				if ($.isArray(value)) {
					acc.push([doctype, field, value[0], value[1]]);
				} else {
					acc.push([doctype, field, "=", value]);
				}
			}
			return acc
		}, []) : undefined;

		const sort_by = frappe.route_options.sort_by || undefined;
		const sort_order = frappe.route_options.sort_order || undefined;

		return {
			filters,
			sort_by,
			sort_order
		}
	}

	get_presets_args() {
		return {}
	}

	get_settings_args() {
		return {
			filters: this.settings.filters ? this.settings.filters.map((f) => {
				if (f.length === 3) {
					f = [this.doctype, f[0], f[1], f[2]];
				}
				return f;
			}) : undefined,
			sort_by:  this.settings.sort_by || undefined,
			sort_order: this.settings.sort_order || undefined,
		}
	}

	get_default_args() {
		return {
			start: 0,
			page_length: 20,
			fields: [],
			filters: [],
			sort_by:  this.meta.sort_field || "modified",
			sort_order:  (this.meta.sort_order || "desc").toLowerCase()
		}
	}

	setup_fields() {
		this.set_fields();
		this.build_fields();
	}

	set_fields() {
		let fields = [].concat(
			frappe.model.std_fields_list,
			this.meta.title_field
		);

		fields.forEach((f) => this._add_field(f));
	}

	get_fields_in_list_view() {
		return this.meta.fields.filter((df) => {
			return (
				(frappe.model.is_value_type(df.fieldtype) &&
					(df.in_list_view &&
						frappe.perm.has_perm(
							this.doctype,
							df.permlevel,
							"read"
						))) ||
				(df.fieldtype === "Currency" &&
					df.options &&
					!df.options.includes(":")) ||
				df.fieldname === "status"
			);
		});
	}

	build_fields() {
		// fill in missing doctype
		this.fields = this.fields.map((f) => {
			if (typeof f === "string") {
				f = [f, this.doctype];
			}
			return f;
		});
		// remove null or undefined values
		this.fields = this.fields.filter(Boolean);
		//de-duplicate
		this.fields = this.fields.uniqBy((f) => f[0] + f[1]);
	}

	_add_field(fieldname, doctype) {
		if (!fieldname) return;

		if (!doctype) doctype = this.doctype;

		if (typeof fieldname === "object") {
			// df is passed
			const df = fieldname;
			fieldname = df.fieldname;
			doctype = df.parent || doctype;
		}

		if (!this.fields) this.fields = [];
		const is_valid_field =
			frappe.model.std_fields_list.includes(fieldname) ||
			frappe.meta.has_field(doctype, fieldname) ||
			fieldname === "_seen";

		if (!is_valid_field) {
			return;
		}

		this.fields.push([fieldname, doctype]);
	}

	set_stats() {
		this.stats = ["_user_tags"];
		// add workflow field (as priority)
		this.workflow_state_fieldname = frappe.workflow.get_state_fieldname(
			this.doctype
		);
		if (this.workflow_state_fieldname) {
			if (!frappe.workflow.workflows[this.doctype]["override_status"]) {
				this._add_field(this.workflow_state_fieldname);
			}
			this.stats.push(this.workflow_state_fieldname);
		}
	}

	fetch_meta() {
		return frappe.model.with_doctype(this.doctype);
	}

	show_skeleton() {

	}

	hide_skeleton() {

	}

	check_permissions() {
		return true;
	}

	setup_page() {
		this.page = this.parent.page;
		this.$page = $(this.parent);
		!this.hide_card_layout && this.page.main.addClass('frappe-card');
		this.page.page_form.removeClass("row").addClass("flex");
		this.hide_page_form && this.page.page_form.hide();
		this.hide_sidebar && this.$page.addClass('no-list-sidebar');
		this.setup_page_head();
	}

	setup_page_head() {
		this.set_title();
		this.set_menu_items();
		this.set_breadcrumbs();
	}

	set_title() {
		this.page.set_title(this.page_title);
	}

	setup_view_menu() {
		// TODO: add all icons
		const icon_map = {
			'Image': 'image-view',
			'List': 'list',
			'Report': 'small-file',
			'Calendar': 'calendar',
			'Gantt': 'gantt',
			'Kanban': 'kanban',
			'Dashboard': 'dashboard',
			'Map': 'map',
		};

		if (frappe.boot.desk_settings.view_switcher) {
			/* @preserve
			for translation, don't remove
			__("List View") __("Report View") __("Dashboard View") __("Gantt View"),
			__("Kanban View") __("Calendar View") __("Image View") __("Inbox View"),
			__("Tree View") __("Map View") */
			this.views_menu = this.page.add_custom_button_group(__('{0} View', [this.view_name]),
				icon_map[this.view_name] || 'list');
			this.views_list = new frappe.views.ListViewSelect({
				doctype: this.doctype,
				parent: this.views_menu,
				page: this.page,
				list_view: this,
				sidebar: this.list_sidebar,
				icon_map: icon_map
			});
		}
	}

	set_default_secondary_action() {
		if (this.secondary_action) {
			const $secondary_action = this.page.set_secondary_action(
				this.secondary_action.label,
				this.secondary_action.action,
				this.secondary_action.icon
			);
			if (!this.secondary_action.icon) {
				$secondary_action.addClass("hidden-xs");
			} else if (!this.secondary_action.label) {
				$secondary_action.addClass("visible-xs");
			}
		} else {
			this.refresh_button = this.page.add_action_icon("refresh", () => {
				this.refresh();
			});
		}
	}

	set_menu_items() {
		this.set_default_secondary_action();

		this.menu_items && this.menu_items.map((item) => {
			if (item.condition && item.condition() === false) {
				return;
			}
			const $item = this.page.add_menu_item(
				item.label,
				item.action,
				item.standard,
				item.shortcut
			);
			if (item.class) {
				$item && $item.addClass(item.class);
			}
		});
	}

	set_breadcrumbs() {
		frappe.breadcrumbs.add(this.meta.module, this.doctype);
	}

	setup_side_bar() {
		if (this.hide_sidebar || !frappe.boot.desk_settings.list_sidebar) return;
		this.list_sidebar = new frappe.views.ListSidebar({
			doctype: this.doctype,
			stats: this.stats,
			parent: this.$page.find(".layout-side-section"),
			page: this.page,
			list_view: this,
		});
	}

	toggle_side_bar(show) {
		let show_sidebar = show || JSON.parse(localStorage.show_sidebar || "true");
		show_sidebar = !show_sidebar;
		localStorage.show_sidebar = show_sidebar;
		this.show_or_hide_sidebar();
		$(document.body).trigger("toggleListSidebar");
	}

	show_or_hide_sidebar() {
		let show_sidebar = JSON.parse(localStorage.show_sidebar || "true");
		$(document.body).toggleClass("no-list-sidebar", !show_sidebar);
	}

	setup_main_section() {
		return frappe.run_serially(
			[
				this.setup_list_wrapper,
				this.show_or_hide_sidebar,
				this.setup_filter_area,
				this.setup_sort_selector,
				this.setup_result_area,
				this.setup_no_result_area,
				this.setup_freeze_area,
				this.setup_paging_area,
			].map((fn) => fn.bind(this))
		);
	}

	setup_list_wrapper() {
		this.$frappe_list = $('<div class="frappe-list">').appendTo(
			this.page.main
		);
	}

	setup_filter_area() {
		if (this.hide_filters) return;
		this.filter_area = new FilterArea(this);
		if (this.filters && this.filters.length > 0) {
			return this.filter_area.set(this.filters);
		}
	}

	setup_sort_selector() {
		if (this.hide_sort_selector) return;
		this.sort_selector = new frappe.ui.SortSelector({
			parent: this.$filter_section,
			doctype: this.doctype,
			args: {
				sort_by: this.sort_by,
				sort_order: this.sort_order,
			},
			onchange: this.on_sort_change.bind(this),
		});
	}

	setup_result_area() {
		this.$result = $(`<div class="result">`);
		this.$frappe_list.append(this.$result);
	}

	setup_no_result_area() {
		this.$no_result = $(`
			<div class="no-result text-muted flex justify-center align-center">
				${this.get_no_result_message()}
			</div>
		`).hide();
		this.$frappe_list.append(this.$no_result);
	}

	setup_freeze_area() {
		this.$freeze = $('<div class="freeze"></div>').hide();
		this.$frappe_list.append(this.$freeze);
	}

	get_no_result_message() {
		return __("Nothing to show");
	}

	setup_paging_area() {
		const paging_values = [20, 100, 500];
		this.$paging_area = $(
			`<div class="list-paging-area level">
				<div class="level-left">
					<div class="btn-group">
						${paging_values.map((value) => `
							<button type="button" class="btn btn-default btn-sm btn-paging"
								data-value="${value}">
								${value}
							</button>
						`).join("")}
					</div>
				</div>
				<div class="level-right">
					<button class="btn btn-default btn-more btn-sm">
						${__("Load More")}
					</button>
				</div>
			</div>`
		).hide();

		this.$frappe_list.append(this.$paging_area);

		// set default paging btn active
		this.$paging_area
			.find(`.btn-paging[data-value="${this.page_length}"]`)
			.addClass("btn-info");

		this.$paging_area.on("click", ".btn-paging, .btn-more", (e) => {
			const $this = $(e.currentTarget);

			if ($this.is(".btn-paging")) {
				// set active button
				this.$paging_area.find(".btn-paging").removeClass("btn-info");
				$this.addClass("btn-info");

				this.start = 0;
				this.page_length = this.selected_page_count = $this.data().value;
			} else if ($this.is(".btn-more")) {
				this.start = this.start + this.page_length;
				this.page_length = this.selected_page_count || 20;
			}
			this.refresh();
		});
	}

	get_fields() {
		// convert [fieldname, Doctype] => tabDoctype.fieldname
		return this.fields.map((f) =>
			frappe.model.get_full_column_name(f[0], f[1])
		);
	}

	get_group_by() {
		let name_field = this.fields && this.fields.find(f => f[0] == 'name');
		if (name_field) {
			return frappe.model.get_full_column_name(name_field[0], name_field[1]);
		}
		return null;
	}

	setup_view() {
		// for child classes
	}

	get_filter_value(fieldname) {
		const filter = this.filters.filter(f => f[1] == fieldname)[0];
		if (!filter) return;
		return {
			'like': filter[3]?.replace(/^%?|%$/g, ''),
			'not set': null
		}[filter[2]] || filter[3];
	}

	get_args() {
		return {
			doctype: this.doctype,
			fields: this.get_fields(),
			filters: this.filters,
			order_by: this.sort_selector && this.sort_selector.get_sql_string(),
			start: this.start,
			page_length: this.page_length,
			view: this.view,
			group_by: this.get_group_by()
		};
	}

	get_call_args() {
		const args = this.get_args();
		return {
			method: this.method,
			args: args,
			freeze: this.freeze_on_refresh || false,
			freeze_message: this.freeze_message || __("Loading") + "...",
		};
	}

	before_refresh() {
		// modify args here just before making the request
		// see list_view.js
	}

	refresh() {
		this.freeze(true);
		// fetch data from server
		return frappe.call(this.get_call_args()).then((r) => {
			// render
			this.prepare_data(r);
			this.toggle_result_area();
			this.before_render();
			this.render();
			this.after_render();
			this.freeze(false);
			this.reset_defaults();
			if (this.settings.refresh) this.settings.refresh(this);
		});
	}


	prepare_data(r) {
		let data = r.message || {};

		// extract user_info for assignments
		Object.assign(frappe.boot.user_info, data.user_info);
		delete data.user_info;

		data = !Array.isArray(data)
			? frappe.utils.dict(data.keys, data.values)
			: data;

		if (this.start === 0) {
			this.data = data;
		} else {
			this.data = this.data.concat(data);
		}

		this.data = this.data.uniqBy((d) => d.name);
	}

	reset_defaults() {
		this.page_length = this.page_length + this.start;
		this.start = 0;
	}

	freeze() {
		// show a freeze message while data is loading
	}

	before_render() {}
	after_render() {}
	render() {}

	resolve_route_options() {
		return {
			filters: this.filters.reduce((acc, [doctype, field, op, value]) => {
				field = doctype !== this.doctype ? `${doctype}.${field}` : field
				acc[field] = op === '=' ? value : [op, value]
				return acc
			}, {}),
			sort_by: this.sort_by,
			sort_order: this.sort_order,
		}
	}

	update_route_options() {
		frappe.router.replace_route_options({
			...frappe.route_options,
			...this.resolve_route_options()
		});
	}

	on_filter_change(filters) {
		this.filters = filters
		this.start = 0
		this.update_route_options()
		this.refresh()
	}

	on_sort_change(sort_by, sort_order) {
		this.sort_by = sort_by;
		this.sort_order = sort_order;
		this.update_route_options()
		this.refresh()
	}

	toggle_result_area() {
		this.$result.toggle(this.data.length > 0);
		this.$paging_area.toggle(this.data.length > 0);
		this.$no_result.toggle(this.data.length == 0);
		const show_more = this.start + this.page_length <= this.data.length;
		this.$paging_area.find(".btn-more").toggle(show_more);
	}

	call_for_selected_items(method, args = {}) {
		args.names = this.get_checked_items(true);

		frappe.call({
			method: method,
			args: args,
			freeze: true,
			callback: (r) => {
				if (!r.exc) {
					this.refresh();
				}
			},
		});
	}
};

class FilterArea {
	constructor(list_view) {
		this.list_view = list_view;
		this.list_view.page.page_form.append(`<div class="standard-filter-section flex"></div>`);

		const filter_area = this.list_view.hide_page_form
			? this.list_view.page.custom_actions
			: this.list_view.page.page_form;

		this.list_view.$filter_section = $('<div class="filter-section flex">').appendTo(
			filter_area
		);

		this.$filter_list_wrapper = this.list_view.$filter_section;
		this.prevent_onchange = false;
		this.prev_filters = null;
		this.setup();
	}

	setup() {
		if (!this.list_view.hide_page_form) {
			this.make_standard_filters();
		}
		this.make_filter_list();
	}

	get() {
		let filters = this.filter_list.get_filters();
		let standard_filters = this.get_standard_filters();
		return filters.concat(standard_filters).map((filter) => filter.slice(0, 4)).uniqBy(JSON.stringify);
	}

	get_standard_filters() {
		const filters = [];
		const fields_dict = this.list_view.page.fields_dict;
		for (let key in fields_dict) {
			let field = fields_dict[key];
			let value = field.get_value();

			if (value) {
				if (field.df.condition === "like" && !value.includes("%")) {
					value = "%" + value + "%";
				}
				filters.push([
					this.list_view.doctype,
					field.df.fieldname,
					field.df.condition || "=",
					value,
				]);
			}
		}

		return filters;
	}

	async set(filters) {
		// use to method to set filters without triggering refresh
		await this._clear();
		await this._add(filters);
	}

	async add() {
		await this._add.apply(this, arguments);
		this.onchange();
	}

	async _add(filters) {
		this.prevent_onchange = true;
		const fields_dict = this.list_view.page.fields_dict;

		if (typeof filters[0] === "string") {
			// passed in the format of doctype, field, condition, value
			filters = [Array.from(arguments)];
		}

		filters = filters.filter(filter => !this.exists(filter));
		const [standard_filters, non_standard_filters] = filters.reduce((acc, filter) => {
			const [dt, fieldname, condition, value] = filter;
			if (
				fields_dict[fieldname] &&
				(
					condition === "=" ||
					(condition === "like" && fields_dict[fieldname]?.df?.fieldtype != "Link")
				)
			) {
				acc[0].push(filter)
			} else {
				acc[1].push(filter)
			}
			return acc;
		}, [[], []]);

		await Promise.all([
			this.filter_list.add_filters(non_standard_filters),
			Promise.all(standard_filters.map((filter) => {
				const [dt, fieldname, condition, value] = filter;
				return fields_dict[fieldname].set_value(value)
			}))
		])

		this.prevent_onchange = false;
	}

	async remove(filters) {
		await this._remove.apply(this, arguments);
		this.onchange();
	}

	async _remove(filters) {
		this.prevent_onchange = true;
		const fields_dict = this.list_view.page.fields_dict;
		const fieldnames = typeof filters === "string" ? [filters] : filters.map((filter) => filter[1])

		await Promise.all(
			fieldnames
				.filter(fieldname => fields_dict[fieldname] !== undefined)
				.map(fieldname => fields_dict[fieldname].set_value(""))
		);

		fieldnames
			.filter(fieldname => fields_dict[fieldname] === undefined)
			.forEach(fieldname => {
				const filter = this.filter_list.get_filter(fieldname);
				if (filter) {
					filter.remove();
				}
		});

		this.filter_list.apply();
		this.prevent_onchange = false;
	}

	async clear() {
		await this._clear()
		this.onchange()
	}

	async _clear() {
		this.prevent_onchange = true;
		this.filter_list.clear_filters();
		await Promise.all(Object.values(this.list_view.page.fields_dict).map(field => field.set_value("")))
		this.prevent_onchange = false;
	}

	exists(filter) {
		// check in standard filters
		const fields_dict = this.list_view.page.fields_dict;
		if (filter[2] === "=" && filter[1] in fields_dict) {
			const value = fields_dict[filter[1]].get_value();
			if (value) {
				return true
			}
		}

		return this.filter_list.filter_exists(filter);
	}

	onchange() {
		if (!this.prevent_onchange) {
			const next_filters = this.get();
			// Should be removed once all edge cases are solved
			const changed = !frappe.utils.deep_equal(next_filters, this.prev_filters)
			this.prev_filters = next_filters
			if (changed) {
				this.list_view.on_filter_change(this.get());
			}
		}
	}

	make_standard_filters() {
		this.standard_filters_wrapper = this.list_view.page.page_form.find('.standard-filter-section');
		let fields = [
			{
				fieldtype: "Data",
				label: "ID",
				condition: "like",
				fieldname: "name",
				onchange: this.onchange.bind(this),
			},
		];

		if (this.list_view.custom_filter_configs) {
			this.list_view.custom_filter_configs.forEach((config) => {
				config.onchange =  this.onchange.bind(this);
			});

			fields = fields.concat(this.list_view.custom_filter_configs);
		}

		const doctype_fields = this.list_view.meta.fields;
		const title_field = this.list_view.meta.title_field;
		const has_existing_filters = (
			this.list_view.filters
			&& this.list_view.filters.length > 0
		);

		fields = fields.concat(
			doctype_fields
				.filter(
					(df) =>
						df.fieldname === title_field ||
						(df.in_standard_filter &&
							frappe.model.is_value_type(df.fieldtype))
				)
				.map((df) => {
					let options = df.options;
					let condition = "=";
					let fieldtype = df.fieldtype;
					if (
						[
							"Text",
							"Small Text",
							"Text Editor",
							"HTML Editor",
							"Data",
							"Code",
							"Read Only",
						].includes(fieldtype)
					) {
						fieldtype = "Data";
						condition = "like";
					}
					if (df.fieldtype == "Select" && df.options) {
						options = df.options.split("\n");
						if (options.length > 0 && options[0] != "") {
							options.unshift("");
							options = options.join("\n");
						}
					}

					let default_value;

					if (fieldtype === "Link" && !has_existing_filters) {
						default_value = frappe.defaults.get_user_default(options);
					}

					if (["__default", "__global"].includes(default_value)) {
						default_value = null;
					}

					return {
						fieldtype: fieldtype,
						label: __(df.label),
						options: options,
						fieldname: df.fieldname,
						condition: condition,
						default: default_value,
						onchange: this.onchange.bind(this),
						ignore_link_validation: fieldtype === "Dynamic Link",
						is_filter: 1,
					};
				})
		);

		fields.map(df => {
			this.list_view.page.add_field(df, this.standard_filters_wrapper);
		});
	}

	make_filter_list() {
		$(`<div class="filter-selector">
			<button class="btn btn-default btn-sm filter-button">
				<span class="filter-icon">
					${frappe.utils.icon('filter')}
				</span>
				<span class="button-label hidden-xs">
					${__("Filter")}
				<span>
			</button>
		</div>`
		).appendTo(this.$filter_list_wrapper);

		this.filter_button = this.$filter_list_wrapper.find('.filter-button');
		this.filter_list = new frappe.ui.FilterGroup({
			parent: this.$filter_list_wrapper,
			doctype: this.list_view.doctype,
			filter_button: this.filter_button,
			default_filters: [],
			on_change:  this.onchange.bind(this),
		});
	}

	is_being_edited() {
		// returns true if user is currently editing filters
		return (
			this.filter_list &&
			this.filter_list.wrapper &&
			this.filter_list.wrapper.find(".filter-box:visible").length > 0
		);
	}
}

// utility function to validate view modes
frappe.views.view_modes = [
	"List",
	"Report",
	"Dashboard",
	"Gantt",
	"Kanban",
	"Calendar",
	"Image",
	"Inbox",
	"Tree",
	"Map",
];
frappe.views.is_valid = (view_mode) =>
	frappe.views.view_modes.includes(view_mode);
