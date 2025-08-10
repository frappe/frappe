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

	init() {
		if (this.init_promise) return this.init_promise;

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

		this.init_promise = frappe.run_serially(tasks);
		return this.init_promise;
	}

	setup_defaults() {
		this.page_name = frappe.get_route_str();
		this.page_title = this.page_title || frappe.router.doctype_layout || __(this.doctype);
		this.meta = frappe.get_meta(this.doctype);
		this.settings = frappe.listview_settings[this.doctype] || {};
		this.user_settings = frappe.get_user_settings(this.doctype);

		this.start = 0;
		this.page_length = frappe.is_large_screen() ? 100 : 20;
		this.selected_page_count = this.page_length;
		this.data = [];
		this.method = "frappe.desk.reportview.get";

		this.can_create = frappe.model.can_create(this.doctype);
		this.can_write = frappe.model.can_write(this.doctype);

		this.fields = [];
		this.filters = [];
		this.sort_by = this.meta.sort_field || "creation";
		this.sort_order = this.meta.sort_order || "desc";

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

	get_list_view_settings() {
		return frappe
			.call("frappe.desk.listview.get_list_settings", {
				doctype: this.doctype,
			})
			.then((doc) => (this.list_view_settings = doc.message || {}));
	}

	async setup_fields() {
		await this.set_fields();
		this.build_fields();
	}

	async set_fields() {
		let fields = [].concat(frappe.model.std_fields_list, this.meta.title_field);

		fields.forEach((f) => this._add_field(f));
	}

	get_fields_in_list_view() {
		return this.meta.fields.filter((df) => {
			return (
				(frappe.model.is_value_type(df.fieldtype) &&
					df.in_list_view &&
					frappe.perm.has_perm(this.doctype, df.permlevel, "read")) ||
				(df.fieldtype === "Currency" && df.options && !df.options.includes(":")) ||
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

		let is_virtual = this.meta.fields.find((df) => df.fieldname == fieldname)?.is_virtual;

		if (!is_valid_field || is_virtual) {
			return;
		}

		this.fields.push([fieldname, doctype]);
	}

	set_stats() {
		this.stats = ["_user_tags"];
		// add workflow field (as priority)
		this.workflow_state_fieldname = frappe.workflow.get_state_fieldname(this.doctype);
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

	show_skeleton() {}

	hide_skeleton() {}

	check_permissions() {
		return true;
	}

	setup_page() {
		this.page = this.parent.page;
		this.$page = $(this.parent);
		this.page.main.addClass("layout-main-list");
		this.page.page_form.removeClass("row").addClass("flex");
		this.hide_page_form && this.page.page_form.hide();
		this.setup_page_head();
	}

	setup_page_head() {
		this.set_title();
		this.set_menu_items();
		this.set_breadcrumbs();
	}

	set_title() {
		this.page.set_title(this.page_title, null, true, "", this.meta?.description);
	}

	setup_view_menu() {
		if (frappe.boot.desk_settings.view_switcher && !this.meta.force_re_route_to_default_view) {
			const icon_map = {
				Image: "image-view",
				List: "list",
				Report: "small-file",
				Calendar: "calendar",
				Gantt: "gantt",
				Kanban: "kanban",
				Dashboard: "dashboard",
				Map: "map",
			};

			const label_map = {
				List: __("List View"),
				Report: __("Report View"),
				Dashboard: __("Dashboard View"),
				Gantt: __("Gantt View"),
				Kanban: __("Kanban View"),
				Calendar: __("Calendar View"),
				Image: __("Image View"),
				Inbox: __("Inbox View"),
				Tree: __("Tree View"),
				Map: __("Map View"),
			};

			this.views_menu = this.page.add_custom_button_group(
				label_map[this.view_name] || label_map["List"],
				icon_map[this.view_name] || "list"
			);
			this.views_list = new frappe.views.ListViewSelect({
				doctype: this.doctype,
				parent: this.views_menu,
				page: this.page,
				list_view: this,
				sidebar: this.list_sidebar,
				icon_map: icon_map,
				label_map: label_map,
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
			this.refresh_button = this.page.add_action_icon(
				"es-line-reload",
				() => {
					this.refresh();
				},
				"",
				__("Reload List")
			);
		}
	}

	set_menu_items() {
		this.set_default_secondary_action();

		this.menu_items &&
			this.menu_items.map((item) => {
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
		if (this.page.disable_sidebar_toggle) {
			return;
		}

		this.list_sidebar = new frappe.views.ListSidebar({
			doctype: this.doctype,
			stats: this.stats,
			parent: this.$page.find(".layout-side-section"),
			page: this.page,
			list_view: this,
		});
	}

	toggle_side_bar(show) {
		frappe.app.sidebar.toggle_sidebar();
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
				this.setup_result_container_area,
				this.setup_result_area,
				this.setup_no_result_area,
				this.setup_freeze_area,
				this.setup_paging_area,
			].map((fn) => fn.bind(this))
		);
	}

	setup_list_wrapper() {
		this.$frappe_list = $('<div class="frappe-list">').appendTo(this.page.main);
	}

	setup_filter_area() {
		if (this.hide_filters) return;
		this.filter_area = new FilterArea(this);

		if (this.filters && this.filters.length > 0) {
			return this.filter_area.set(this.filters).catch(() => {
				this.filter_area.clear(false);
			});
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

	on_sort_change() {
		this.refresh();
	}

	/**
	 * Sets up a result container area by appending a new `<div>` element with the class `result-container`
	 * to the `frappe_list` container. This container is used to create a scrollable area for the result content.
	 */
	setup_result_container_area() {
		this.$frappe_list.append($(`<div class="result-container">`));
	}

	setup_result_area() {
		this.$result = $(`<div class="result">`);
		this.$frappe_list.find(".result-container").append(this.$result);
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
		const paging_values = [20, 100, 500, 2500];
		this.$paging_area = $(
			`<div class="list-paging-area level">
				<div class="level-left">
					<div class="btn-group">
						${paging_values
							.map(
								(value) => `
							<button type="button" class="btn btn-default btn-sm btn-paging"
								data-value="${value}">
								${value}
							</button>
						`
							)
							.join("")}
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
			.addClass("btn-info")
			.prop("disabled", true);

		this.$paging_area.on("click", ".btn-paging", (e) => {
			const $this = $(e.currentTarget);
			// Set the active button
			// This is always necessary because the current page length might
			// have resulted from a previous "load more".
			this.$paging_area.find(".btn-paging").removeClass("btn-info").prop("disabled", false);
			$this.addClass("btn-info").prop("disabled", true);

			const old_page_length = this.page_length;
			const new_page_length = $this.data().value;

			this.selected_page_count = new_page_length;
			if (this.page_length > new_page_length) {
				this.start = 0;
				this.page_length = new_page_length;
			} else {
				this.start = this.page_length;
				this.page_length = new_page_length - this.page_length;
			}

			if (old_page_length !== new_page_length) {
				this.refresh();
			}
		});

		this.$paging_area.on("click", ".btn-more", (e) => {
			this.start = this.data.length;
			this.page_length = this.selected_page_count;
			this.refresh();
		});
	}

	set_result_height() {
		// place it at the footer of the page
		this.$result.css({
			height:
				window.innerHeight -
				this.$result.get(0).offsetTop -
				this.$paging_area.get(0).offsetHeight +
				"px",
		});
		this.$no_result.css({
			height: window.innerHeight - this.$no_result.get(0).offsetTop + "px",
		});
	}

	get_fields() {
		// convert [fieldname, Doctype] => tabDoctype.fieldname
		return this.fields.map((f) => frappe.model.get_full_column_name(f[0], f[1]));
	}

	get_group_by() {
		let name_field = this.fields && this.fields.find((f) => f[0] == "name");
		if (name_field) {
			return frappe.model.get_full_column_name(name_field[0], name_field[1]);
		}
		return null;
	}

	setup_view() {
		// for child classes
	}

	get_filter_value(fieldname) {
		const filter = this.get_filters_for_args().filter((f) => f[1] == fieldname)[0];
		if (!filter) return;
		if (filter[2] === "like") return filter[3]?.replace(/^%?|%$/g, "");
		else if (filter[2] === "not set") return null;
		else return filter[3];
	}

	get_filters_for_args() {
		// filters might have a fifth param called hidden,
		// we don't want to pass that server side
		return this.filter_area ? this.filter_area.get().map((filter) => filter.slice(0, 4)) : [];
	}

	get_args() {
		let filters = this.get_filters_for_args();
		let group_by = this.get_group_by();
		let group_by_required =
			Array.isArray(filters) &&
			filters.some((filter) => {
				return filter[0] !== this.doctype;
			});
		return {
			doctype: this.doctype,
			fields: this.get_fields(),
			filters,
			order_by: this.sort_selector && this.sort_selector.get_sql_string(),
			start: this.start,
			page_length: this.page_length,
			view: this.view,
			group_by: group_by_required ? group_by : null,
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
		let args = this.get_call_args();
		if (this.no_change(args)) {
			// console.log('throttled');
			return Promise.resolve();
		}
		this.freeze(true);
		// fetch data from server
		return frappe.call(args).then((r) => {
			// render
			this.prepare_data(r);
			this.toggle_result_area();
			this.before_render();
			this.render();
			this.after_render();
			this.set_result_height();
			this.freeze(false);
			this.reset_defaults();
			if (this.settings.refresh) {
				this.settings.refresh(this);
			}
		});
	}

	no_change(args) {
		// returns true if arguments are same for the last 3 seconds
		// this helps in throttling if called from various sources
		if (this.last_args && JSON.stringify(args) === this.last_args) {
			return true;
		}
		this.last_args = JSON.stringify(args);
		setTimeout(() => {
			this.last_args = null;
		}, 3000);
		return false;
	}

	prepare_data(r) {
		let data = r.message || {};

		// extract user_info for assignments
		Object.assign(frappe.boot.user_info, data.user_info);
		delete data.user_info;

		data = !Array.isArray(data) ? frappe.utils.dict(data.keys, data.values) : data;

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

	render() {
		// for child classes
	}

	on_filter_change() {
		// fired when filters are added or removed
	}

	toggle_result_area() {
		this.$result.toggle(this.data.length > 0);
		this.$paging_area.toggle(this.data.length > 0);
		this.$no_result.toggle(this.data.length == 0);

		if (this.data.length) {
			const show_more = this.start + this.page_length <= this.data.length;
			this.$paging_area.find(".btn-more").toggle(show_more);
		}
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
		this.trigger_refresh = true;

		this.debounced_refresh_list_view = frappe.utils.debounce(
			this.refresh_list_view.bind(this),
			300
		);
		this.setup();
		if (frappe.is_mobile()) this.setup_mobile(list_view);
	}
	setup_mobile(list_view) {
		const me = this;
		this.standard_filters_visible = false;
		this.standard_filters_wrapper.hide();
		this.list_view.page.page_form.css("justify-content", "flex-end");
		$(`<button class="filter-toggle btn btn-default btn-sm filter-button">
					<span class="filter-icon button-icon">
						${frappe.utils.icon("funnel-plus")}
					</span>
				</button>
			</div>`)
			.prependTo(this.$filter_list_wrapper.find(".filter-selector"))
			.on("click", function () {
				me.toggle_standard_filter();
			});
		let children = list_view.page.page_form.children();
		list_view.page.page_form.append(children.get().reverse());
	}

	toggle_standard_filter() {
		if (this.standard_filters_visible) {
			this.standard_filters_visible = false;
			this.standard_filters_wrapper.hide();
		} else {
			this.standard_filters_visible = true;
			this.standard_filters_wrapper.show();
		}
		let icon_name = !this.standard_filters_visible ? "funnel-plus" : "funnel-x";
		this.$filter_list_wrapper
			.find(".filter-toggle")
			.find("use")
			.attr("href", `#icon-${icon_name}`);
	}

	setup() {
		if (!this.list_view.hide_page_form) this.make_standard_filters();
		this.make_filter_list();
	}

	get() {
		let filters = this.filter_list.get_filters();
		let standard_filters = this.get_standard_filters();

		return filters.concat(standard_filters).uniqBy(JSON.stringify);
	}

	set(filters) {
		// use to method to set filters without triggering refresh
		this.trigger_refresh = false;
		return this.add(filters, false).then(() => {
			this.trigger_refresh = true;
			this.filter_list.update_filter_button();
		});
	}

	add(filters, refresh = true) {
		if (!filters || (Array.isArray(filters) && filters.length === 0)) return Promise.resolve();

		if (typeof filters[0] === "string") {
			// passed in the format of doctype, field, condition, value
			const filter = Array.from(arguments);
			filters = [filter];
		}

		filters = filters.filter((f) => !this.exists(f));

		// standard filters = filters visible on list view
		// non-standard filters = filters set by filter button
		const { non_standard_filters, promise } = this.set_standard_filter(filters);

		return promise
			.then(() => {
				return (
					non_standard_filters.length > 0 &&
					this.filter_list.add_filters(non_standard_filters)
				);
			})
			.then(() => {
				refresh && this.list_view.refresh();
			});
	}

	refresh_list_view() {
		if (this.trigger_refresh) {
			this.list_view.start = 0;
			this.list_view.refresh();
			this.list_view.on_filter_change();
		}
	}

	exists(f) {
		let exists = false;
		// check in standard filters
		const fields_dict = this.list_view.page.fields_dict;
		if (f[2] === "=" && f[1] in fields_dict) {
			const value = fields_dict[f[1]].get_value();
			if (value) {
				exists = true;
			}
		}

		// check in filter area
		if (!exists) {
			exists = this.filter_list.filter_exists(f);
		}

		return exists;
	}

	set_standard_filter(filters) {
		if (filters.length === 0) {
			return {
				non_standard_filters: [],
				promise: Promise.resolve(),
			};
		}

		const fields_dict = this.list_view.page.fields_dict;

		return filters.reduce((out, filter) => {
			const [dt, fieldname, condition, value] = filter;
			out.promise = out.promise || Promise.resolve();
			out.non_standard_filters = out.non_standard_filters || [];

			// set in list view area if filters are present
			// don't set like filter on link fields (gets reset)
			if (
				fields_dict[fieldname] &&
				(condition === "=" ||
					(condition === "like" && fields_dict[fieldname]?.df?.fieldtype != "Link") ||
					(condition === "descendants of (inclusive)" &&
						fields_dict[fieldname]?.df?.fieldtype == "Link"))
			) {
				// standard filter
				out.promise = out.promise.then(() => fields_dict[fieldname].set_value(value));
			} else {
				// filter out non standard filters
				out.non_standard_filters.push(filter);
			}
			return out;
		}, {});
	}

	remove_filters(filters) {
		filters.map((f) => {
			this.remove(f[1]);
		});
	}

	remove(fieldname) {
		const fields_dict = this.list_view.page.fields_dict;

		if (fieldname in fields_dict) {
			fields_dict[fieldname].set_value("");
		}

		let filter = this.filter_list.get_filter(fieldname);
		if (filter) filter.remove();
		this.filter_list.apply();
		return Promise.resolve();
	}

	clear(refresh = true) {
		if (!refresh) {
			this.trigger_refresh = false;
		}

		this.filter_list.clear_filters();

		const promises = [];
		const fields_dict = this.list_view.page.fields_dict;
		for (let key in fields_dict) {
			const field = this.list_view.page.fields_dict[key];
			promises.push(() => field.set_value(""));
		}
		return frappe.run_serially(promises).then(() => {
			this.trigger_refresh = true;
			if (promises.length === 0) {
				// refresh if there are no standard fields
				this.debounced_refresh_list_view();
			}
		});
	}

	async make_standard_filters() {
		this.standard_filters_wrapper = this.list_view.page.page_form.find(
			".standard-filter-section"
		);
		let fields = [];

		if (!this.list_view.settings.hide_name_filter) {
			fields.push({
				fieldtype: "Data",
				label: "ID",
				condition: "like",
				fieldname: "name",
				onchange: () => this.debounced_refresh_list_view(),
			});
		}

		if (
			this.list_view.custom_filter_configs ||
			this.list_view.settings.custom_filter_configs
		) {
			const custom_filter_configs =
				this.list_view.custom_filter_configs ||
				this.list_view.settings.custom_filter_configs;
			await Promise.resolve(
				typeof custom_filter_configs === "function"
					? custom_filter_configs()
					: custom_filter_configs
			).then((configs) => {
				configs.forEach((config) => {
					config.onchange = () => this.debounced_refresh_list_view();
				});

				fields = fields.concat(configs);
			});
		}

		const doctype_fields = this.list_view.meta.fields;
		const title_field = this.list_view.meta.title_field;

		fields = fields.concat(
			doctype_fields
				.filter(
					(df) =>
						(df.fieldname === title_field ||
							(df.in_standard_filter && frappe.model.is_value_type(df.fieldtype))) &&
						frappe.perm.has_perm(this.list_view.doctype, df.permlevel)
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
							"Phone",
							"JSON",
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
					if (
						df.fieldtype == "Link" &&
						df.options &&
						frappe.boot.treeviews.includes(df.options)
					) {
						condition = "descendants of (inclusive)";
					}

					return {
						fieldtype: fieldtype,
						label: __(df.label, null, df.parent),
						options: options,
						fieldname: df.fieldname,
						condition: condition,
						onchange: () => this.debounced_refresh_list_view(),
						ignore_link_validation: fieldtype === "Dynamic Link",
						is_filter: 1,
					};
				})
		);

		fields.map((df) => {
			this.list_view.page.add_field(df, this.standard_filters_wrapper);
		});
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
					field.df.doctype || this.list_view.doctype,
					field.df.fieldname,
					field.df.condition || "=",
					value,
				]);
			}
		}

		return filters;
	}

	make_filter_list() {
		$(`<div class="filter-selector">
			<div class="btn-group">
				<button class="btn btn-default btn-sm filter-button">
					<span class="filter-icon button-icon">
						${frappe.utils.icon("es-line-filter")}
					</span>
					<span class="button-label hidden-xs">
					${__("Filter")}
					<span>
				</button>
				<button class="btn btn-default btn-sm filter-x-button" title="${__("Clear all filters")}">
					<span class="filter-icon button-icon">
						${frappe.utils.icon("es-small-close")}
					</span>
				</button>
			</div>
		</div>`).appendTo(this.$filter_list_wrapper);

		this.filter_button = this.$filter_list_wrapper.find(".filter-button");
		this.filter_x_button = this.$filter_list_wrapper.find(".filter-x-button");
		this.filter_list = new frappe.ui.FilterGroup({
			base_list: this.list_view,
			parent: this.$filter_list_wrapper,
			doctype: this.list_view.doctype,
			filter_button: this.filter_button,
			filter_x_button: this.filter_x_button,
			default_filters: [],
			on_change: () => this.debounced_refresh_list_view(),
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
frappe.views.is_valid = (view_mode) => frappe.views.view_modes.includes(view_mode);
