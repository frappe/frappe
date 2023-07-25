import BulkOperations from "./bulk_operations";
import ListSettings from "./list_settings";

frappe.provide("frappe.views");

frappe.views.ListView = class ListView extends frappe.views.BaseList {
	static load_last_view() {
		const route = frappe.get_route();
		const doctype = route[1];

		if (route.length === 2) {
			const user_settings = frappe.get_user_settings(doctype);
			const last_view = user_settings.last_view;
			frappe.set_route(
				"list",
				frappe.router.doctype_layout || doctype,
				frappe.views.is_valid(last_view) ? last_view.toLowerCase() : "list"
			);
			return true;
		}
		return false;
	}

	constructor(opts) {
		super(opts);
		this.show();
		this.debounced_refresh = frappe.utils.debounce(
			this.process_document_refreshes.bind(this),
			2000
		);
	}

	has_permissions() {
		const can_read = frappe.perm.has_perm(this.doctype, 0, "read");
		return can_read;
	}

	show() {
		this.parent.disable_scroll_to_top = true;
		super.show();
	}

	check_permissions() {
		if (!this.has_permissions()) {
			frappe.set_route("");
			frappe.throw(__("Not permitted to view {0}", [this.doctype]));
		}
	}

	show_skeleton() {
		this.$list_skeleton = this.parent.page.container.find(".list-skeleton");
		if (!this.$list_skeleton.length) {
			this.$list_skeleton = $(`
				<div class="row list-skeleton">
					<div class="col-lg-2">
						<div class="list-skeleton-box"></div>
					</div>
					<div class="col">
						<div class="list-skeleton-box"></div>
					</div>
				</div>
			`);
			this.parent.page.container.find(".page-content").append(this.$list_skeleton);
		}
		this.parent.page.container.find(".layout-main").hide();
		this.$list_skeleton.show();
	}

	hide_skeleton() {
		this.$list_skeleton && this.$list_skeleton.hide();
		this.parent.page.container.find(".layout-main").show();
	}

	get view_name() {
		return "List";
	}

	get view_user_settings() {
		return this.user_settings[this.view_name] || {};
	}

	setup_defaults() {
		super.setup_defaults();

		this.view = "List";
		// initialize with saved order by
		this.sort_by = this.view_user_settings.sort_by || this.sort_by || "modified";
		this.sort_order = this.view_user_settings.sort_order || this.sort_order || "desc";

		// build menu items
		this.menu_items = this.menu_items.concat(this.get_menu_items());

		// set filters from view_user_settings or list_settings
		if (Array.isArray(this.view_user_settings.filters)) {
			// Priority 1: view_user_settings
			const saved_filters = this.view_user_settings.filters;
			this.filters = this.validate_filters(saved_filters);
		} else {
			// Priority 2: filters in listview_settings
			this.filters = (this.settings.filters || []).map((f) => {
				if (f.length === 3) {
					f = [this.doctype, f[0], f[1], f[2]];
				}
				return f;
			});
		}

		if (this.view_name == "List") this.toggle_paging = true;

		this.patch_refresh_and_load_lib();
		return this.get_list_view_settings();
	}

	on_sort_change(sort_by, sort_order) {
		this.sort_by = sort_by;
		this.sort_order = sort_order;
		super.on_sort_change();
	}

	validate_filters(filters) {
		let valid_fields = this.meta.fields.map((df) => df.fieldname);
		valid_fields = valid_fields.concat(frappe.model.std_fields_list);
		return filters.filter((f) => valid_fields.includes(f[1])).uniqBy((f) => f[1]);
	}

	setup_page() {
		this.parent.list_view = this;
		super.setup_page();
	}

	setup_page_head() {
		super.setup_page_head();
		this.set_primary_action();
		this.set_actions_menu_items();
	}

	set_actions_menu_items() {
		this.actions_menu_items = this.get_actions_menu_items();
		this.workflow_action_menu_items = this.get_workflow_action_menu_items();
		this.workflow_action_items = {};

		const actions = this.actions_menu_items.concat(this.workflow_action_menu_items);
		actions.forEach((item) => {
			const $item = this.page.add_actions_menu_item(item.label, item.action, item.standard);
			if (item.class) {
				$item.addClass(item.class);
			}
			if (item.is_workflow_action && $item) {
				// can be used to dynamically show or hide action
				this.workflow_action_items[item.name] = $item;
			}
		});
	}

	show_restricted_list_indicator_if_applicable() {
		const match_rules_list = frappe.perm.get_match_rules(this.doctype);
		if (match_rules_list.length) {
			this.restricted_list = $(
				`<button class="btn btn-xs restricted-button flex align-center">
					${frappe.utils.icon("restriction", "xs")}
				</button>`
			)
				.click(() => this.show_restrictions(match_rules_list))
				.appendTo(this.page.page_form);
		}
	}

	show_restrictions(match_rules_list = []) {
		frappe.msgprint(
			frappe.render_template("list_view_permission_restrictions", {
				condition_list: match_rules_list,
			}),
			__("Restrictions", null, "Title of message showing restrictions in list view")
		);
	}

	get_fields() {
		return super
			.get_fields()
			.concat(
				Object.entries(this.link_field_title_fields || {}).map(
					(entry) => entry.join(".") + " as " + entry.join("_")
				)
			);
	}

	async set_fields() {
		this.link_field_title_fields = {};
		let fields = [].concat(
			frappe.model.std_fields_list,
			this.get_fields_in_list_view(),
			[this.meta.title_field, this.meta.image_field],
			this.settings.add_fields || [],
			this.meta.track_seen ? "_seen" : null,
			this.sort_by,
			"enabled",
			"disabled",
			"color"
		);

		await Promise.all(
			fields.map((f) => {
				return new Promise((resolve) => {
					const df =
						typeof f === "string" ? frappe.meta.get_docfield(this.doctype, f) : f;
					if (
						df &&
						df.fieldtype == "Link" &&
						frappe.boot.link_title_doctypes.includes(df.options)
					) {
						frappe.model.with_doctype(df.options, () => {
							const meta = frappe.get_meta(df.options);
							if (meta.show_title_field_in_link) {
								this.link_field_title_fields[
									typeof f === "string" ? f : f.fieldname
								] = meta.title_field;
							}

							this._add_field(f);
							resolve();
						});
					} else {
						this._add_field(f);
						resolve();
					}
				});
			})
		);

		this.fields.forEach((f) => {
			const df = frappe.meta.get_docfield(f[1], f[0]);
			if (df && df.fieldtype === "Currency" && df.options && !df.options.includes(":")) {
				this._add_field(df.options);
			}
		});
	}

	patch_refresh_and_load_lib() {
		// throttle refresh for 1s
		this.refresh = this.refresh.bind(this);
		this.refresh = frappe.utils.throttle(this.refresh, 1000);
		this.load_lib = new Promise((resolve) => {
			if (this.required_libs) {
				frappe.require(this.required_libs, resolve);
			} else {
				resolve();
			}
		});
		// call refresh every 5 minutes
		const interval = 5 * 60 * 1000;
		setInterval(() => {
			// don't call if route is different
			if (frappe.get_route_str() === this.page_name) {
				this.refresh();
			}
		}, interval);
	}

	set_primary_action() {
		if (this.can_create && !frappe.boot.read_only) {
			const doctype_name = __(frappe.router.doctype_layout) || __(this.doctype);

			// Better style would be __("Add {0}", [doctype_name], "Primary action in list view")
			// Keeping it like this to not disrupt existing translations
			const label = `${__("Add", null, "Primary action in list view")} ${doctype_name}`;
			this.page.set_primary_action(
				label,
				() => {
					if (this.settings.primary_action) {
						this.settings.primary_action();
					} else {
						this.make_new_doc();
					}
				},
				"add"
			);
		} else {
			this.page.clear_primary_action();
		}
	}

	make_new_doc() {
		const doctype = this.doctype;
		const options = {};
		this.filter_area.get().forEach((f) => {
			if (f[2] === "=" && frappe.model.is_non_std_field(f[1])) {
				options[f[1]] = f[3];
			}
		});
		frappe.new_doc(doctype, options);
	}

	setup_view() {
		this.setup_columns();
		this.render_header();
		this.render_skeleton();
		this.setup_events();
		this.settings.onload && this.settings.onload(this);
		this.show_restricted_list_indicator_if_applicable();
	}

	refresh_columns(meta, list_view_settings) {
		this.meta = meta;
		this.list_view_settings = list_view_settings;

		this.setup_columns();
		this.refresh(true);
	}

	refresh(refresh_header = false) {
		super.refresh().then(() => {
			this.render_header(refresh_header);
			this.update_checkbox();
			this.update_url_with_filters();
			this.setup_realtime_updates();
		});
	}

	update_checkbox(target) {
		if (!this.$checkbox_actions) return;

		let $check_all_checkbox = this.$checkbox_actions.find(".list-check-all");

		if ($check_all_checkbox.prop("checked") && target && !target.prop("checked")) {
			$check_all_checkbox.prop("checked", false);
		}

		$check_all_checkbox.prop("checked", this.$checks.length === this.data.length);
	}

	setup_freeze_area() {
		this.$freeze = $(
			`<div class="freeze flex justify-center align-center text-muted">
				${__("Loading")}...
			</div>`
		).hide();
		this.$result.append(this.$freeze);
	}

	setup_columns() {
		// setup columns for list view
		this.columns = [];

		const get_df = frappe.meta.get_docfield.bind(null, this.doctype);

		// 1st column: title_field or name
		if (this.meta.title_field) {
			this.columns.push({
				type: "Subject",
				df: get_df(this.meta.title_field),
			});
		} else {
			this.columns.push({
				type: "Subject",
				df: {
					label: __("ID"),
					fieldname: "name",
				},
			});
		}

		this.columns.push({
			type: "Tag",
		});

		// 2nd column: Status indicator
		if (frappe.has_indicator(this.doctype)) {
			// indicator
			this.columns.push({
				type: "Status",
			});
		}

		const fields_in_list_view = this.get_fields_in_list_view();
		// Add rest from in_list_view docfields
		this.columns = this.columns.concat(
			fields_in_list_view
				.filter((df) => {
					if (frappe.has_indicator(this.doctype) && df.fieldname === "status") {
						return false;
					}
					if (!df.in_list_view) {
						return false;
					}
					return df.fieldname !== this.meta.title_field;
				})
				.map((df) => ({
					type: "Field",
					df,
				}))
		);

		if (this.list_view_settings.fields) {
			this.columns = this.reorder_listview_fields();
		}

		// limit max to 8 columns if no total_fields is set in List View Settings
		// Screen with low density no of columns 4
		// Screen with medium density no of columns 6
		// Screen with high density no of columns 8
		let total_fields = 6;

		if (window.innerWidth <= 1366) {
			total_fields = 4;
		} else if (window.innerWidth >= 1920) {
			total_fields = 10;
		}

		this.columns = this.columns.slice(0, this.list_view_settings.total_fields || total_fields);

		if (
			!this.settings.hide_name_column &&
			this.meta.title_field &&
			this.meta.title_field !== "name"
		) {
			this.columns.push({
				type: "Field",
				df: {
					label: __("ID"),
					fieldname: "name",
				},
			});
		}
	}

	reorder_listview_fields() {
		let fields_order = [];
		let fields = JSON.parse(this.list_view_settings.fields);

		//title and tags field is fixed
		fields_order.push(this.columns[0]);
		fields_order.push(this.columns[1]);
		this.columns.splice(0, 2);

		for (let fld in fields) {
			for (let col in this.columns) {
				let field = fields[fld];
				let column = this.columns[col];

				if (column.type == "Status" && field.fieldname == "status_field") {
					fields_order.push(column);
					break;
				} else if (column.type == "Field" && field.fieldname === column.df.fieldname) {
					fields_order.push(column);
					break;
				}
			}
		}

		return fields_order;
	}

	get_documentation_link() {
		if (this.meta.documentation) {
			return `<a href="${this.meta.documentation}" target="blank" class="meta-description small text-muted">Need Help?</a>`;
		}
		return "";
	}

	get_no_result_message() {
		let help_link = this.get_documentation_link();
		let filters = this.filter_area && this.filter_area.get();

		let has_filters_set = filters && filters.length;
		let no_result_message = has_filters_set
			? __("No {0} found with matching filters. Clear filters to see all {0}.", [
					__(this.doctype),
			  ])
			: __("You haven't created a {0} yet", [__(this.doctype)]);
		let new_button_label = has_filters_set
			? __("Create a new {0}", [__(this.doctype)], "Create a new document from list view")
			: __(
					"Create your first {0}",
					[__(this.doctype)],
					"Create a new document from list view"
			  );
		let empty_state_image =
			this.settings.empty_state_image ||
			"/assets/frappe/images/ui-states/list-empty-state.svg";

		const new_button = this.can_create
			? `<p><button class="btn btn-primary btn-sm btn-new-doc hidden-xs">
				${new_button_label}
			</button> <button class="btn btn-primary btn-new-doc visible-xs">
				${__("Create New", null, "Create a new document from list view")}
			</button></p>`
			: "";

		return `<div class="msg-box no-border">
			<div>
				<img src="${empty_state_image}" alt="Generic Empty State" class="null-state">
			</div>
			<p>${no_result_message}</p>
			${new_button}
			${help_link}
		</div>`;
	}

	freeze() {
		if (this.list_view_settings && !this.list_view_settings.disable_count) {
			this.$result
				.find(".list-count")
				.html(`<span>${__("Refreshing", null, "Document count in list view")}...</span>`);
		}
	}

	get_args() {
		const args = super.get_args();

		return Object.assign(args, {
			with_comment_count: true,
		});
	}

	before_refresh() {
		if (frappe.route_options && this.filter_area) {
			this.filters = this.parse_filters_from_route_options();
			frappe.route_options = null;

			if (this.filters.length > 0) {
				return this.filter_area
					.clear(false)
					.then(() => this.filter_area.set(this.filters));
			}
		}

		return Promise.resolve();
	}

	parse_filters_from_settings() {
		return (this.settings.filters || []).map((f) => {
			if (f.length === 3) {
				f = [this.doctype, f[0], f[1], f[2]];
			}
			return f;
		});
	}

	toggle_result_area() {
		super.toggle_result_area();
		this.toggle_actions_menu_button(this.$result.find(".list-row-check:checked").length > 0);
	}

	toggle_actions_menu_button(toggle) {
		if (toggle) {
			this.page.show_actions_menu();
			this.page.clear_primary_action();
		} else {
			this.page.hide_actions_menu();
			this.set_primary_action();
		}
	}

	render_header(refresh_header = false) {
		if (refresh_header) {
			this.$result.find(".list-row-head").remove();
		}
		if (this.$result.find(".list-row-head").length === 0) {
			// append header once
			this.$result.prepend(this.get_header_html());
		}
	}

	render_skeleton() {
		const $row = this.get_list_row_html_skeleton(
			'<div><input type="checkbox" class="render-list-checkbox"/></div>'
		);
		this.$result.append($row);
	}

	before_render() {
		this.settings.before_render && this.settings.before_render();
		frappe.model.user_settings.save(this.doctype, "last_view", this.view_name);
		this.save_view_user_settings({
			filters: this.filter_area && this.filter_area.get(),
			sort_by: this.sort_selector && this.sort_selector.sort_by,
			sort_order: this.sort_selector && this.sort_selector.sort_order,
		});
		this.toggle_paging && this.$paging_area.toggle(false);
	}

	after_render() {
		this.$no_result.html(`
			<div class="no-result text-muted flex justify-center align-center">
				${this.get_no_result_message()}
			</div>
		`);
		this.setup_new_doc_event();
		this.toggle_paging && this.$paging_area.toggle(true);
	}

	render() {
		this.render_list();
		this.set_rows_as_checked();
		this.render_count();
	}

	render_list() {
		// clear rows
		this.$result.find(".list-row-container").remove();
		if (this.data.length > 0) {
			// append rows
			this.$result.append(
				this.data
					.map((doc, i) => {
						doc._idx = i;
						return this.get_list_row_html(doc);
					})
					.join("")
			);
		}
	}

	render_count() {
		if (!this.list_view_settings.disable_count) {
			this.get_count_str().then((str) => {
				this.$result.find(".list-count").html(`<span>${str}</span>`);
			});
		}
	}

	get_header_html() {
		if (!this.columns) {
			return;
		}

		const subject_field = this.columns[0].df;
		let subject_html = `
			<input class="level-item list-check-all" type="checkbox"
				title="${__("Select All")}">
			<span class="level-item list-liked-by-me hidden-xs">
				<span title="${__("Likes")}">${frappe.utils.icon("heart", "sm", "like-icon")}</span>
			</span>
			<span class="level-item">${__(subject_field.label)}</span>
		`;
		const $columns = this.columns
			.map((col) => {
				let classes = [
					"list-row-col ellipsis",
					col.type == "Subject" ? "list-subject level" : "hidden-xs",
					col.type == "Tag" ? "tag-col hide" : "",
					frappe.model.is_numeric_field(col.df) ? "text-right" : "",
				].join(" ");

				return `
				<div class="${classes}">
					${
						col.type === "Subject"
							? subject_html
							: `
						<span>${__((col.df && col.df.label) || col.type)}</span>`
					}
				</div>
			`;
			})
			.join("");

		return this.get_header_html_skeleton($columns, '<span class="list-count"></span>');
	}

	get_header_html_skeleton(left = "", right = "") {
		return `
			<header class="level list-row-head text-muted">
				<div class="level-left list-header-subject">
					${left}
				</div>
				<div class="level-left checkbox-actions">
					<div class="level list-subject">
						<input class="level-item list-check-all" type="checkbox"
							title="${__("Select All")}">
						<span class="level-item list-header-meta"></span>
					</div>
				</div>
				<div class="level-right">
					${right}
				</div>
			</header>
		`;
	}

	get_left_html(doc) {
		return this.columns.map((col) => this.get_column_html(col, doc)).join("");
	}

	get_right_html(doc) {
		return this.get_meta_html(doc);
	}

	get_list_row_html(doc) {
		return this.get_list_row_html_skeleton(this.get_left_html(doc), this.get_right_html(doc));
	}

	get_list_row_html_skeleton(left = "", right = "") {
		return `
			<div class="list-row-container" tabindex="1">
				<div class="level list-row">
					<div class="level-left ellipsis">
						${left}
					</div>
					<div class="level-right text-muted ellipsis">
						${right}
					</div>
				</div>
			</div>
		`;
	}

	get_column_html(col, doc) {
		if (col.type === "Status" || col.df?.options == "Workflow State") {
			let show_workflow_state = col.df?.options == "Workflow State";
			return `
				<div class="list-row-col hidden-xs ellipsis">
					${this.get_indicator_html(doc, show_workflow_state)}
				</div>
			`;
		}

		if (col.type === "Tag") {
			const tags_display_class = !this.tags_shown ? "hide" : "";
			let tags_html = doc._user_tags
				? this.get_tags_html(doc._user_tags, 2)
				: '<div class="tags-empty">-</div>';
			return `
				<div class="list-row-col tag-col ${tags_display_class} hidden-xs ellipsis">
					${tags_html}
				</div>
			`;
		}

		const df = col.df || {};
		const label = df.label;
		const fieldname = df.fieldname;
		const link_title_fieldname = this.link_field_title_fields[fieldname];
		const value = doc[fieldname] || "";
		let value_display = link_title_fieldname
			? doc[fieldname + "_" + link_title_fieldname] || value
			: value;

		let translated_doctypes = frappe.boot?.translated_doctypes || [];
		if (in_list(translated_doctypes, df.options)) {
			value_display = __(value_display);
		}

		const format = () => {
			if (df.fieldtype === "Code") {
				return value;
			} else if (df.fieldtype === "Percent") {
				return `<div class="progress" style="margin: 0px;">
						<div class="progress-bar progress-bar-success" role="progressbar"
							aria-valuenow="${value}"
							aria-valuemin="0" aria-valuemax="100" style="width: ${Math.round(value)}%;">
						</div>
					</div>`;
			} else {
				return frappe.format(value, df, null, doc);
			}
		};

		const field_html = () => {
			let html;
			let _value;
			let strip_html_required =
				df.fieldtype == "Text Editor" ||
				(df.fetch_from && ["Text", "Small Text"].includes(df.fieldtype));

			if (strip_html_required) {
				_value = strip_html(value_display);
			} else {
				_value =
					typeof value_display === "string"
						? frappe.utils.escape_html(value_display)
						: value_display;
			}

			if (df.fieldtype === "Rating") {
				let out_of_ratings = df.options || 5;
				_value = _value * out_of_ratings;
			}

			if (df.fieldtype === "Image") {
				html = df.options
					? `<img src="${doc[df.options]}"
					style="max-height: 30px; max-width: 100%;">`
					: `<div class="missing-image small">
						${frappe.utils.icon("restriction")}
					</div>`;
			} else if (df.fieldtype === "Select") {
				html = `<span class="filterable indicator-pill ${frappe.utils.guess_colour(
					_value
				)} ellipsis"
					data-filter="${fieldname},=,${value}">
					<span class="ellipsis"> ${__(_value)} </span>
				</span>`;
			} else if (df.fieldtype === "Link") {
				html = `<a class="filterable ellipsis"
					data-filter="${fieldname},=,${value}">
					${_value}
				</a>`;
			} else if (
				["Text Editor", "Text", "Small Text", "HTML Editor", "Markdown Editor"].includes(
					df.fieldtype
				)
			) {
				html = `<span class="ellipsis">
					${_value}
				</span>`;
			} else {
				html = `<a class="filterable ellipsis"
					data-filter="${fieldname},=,${frappe.utils.escape_html(value)}">
					${format()}
				</a>`;
			}

			return `<span class="ellipsis"
				title="${__(label)}: ${frappe.utils.escape_html(_value)}">
				${html}
			</span>`;
		};

		const class_map = {
			Subject: "list-subject level",
			Field: "hidden-xs",
		};
		const css_class = [
			"list-row-col ellipsis",
			class_map[col.type],
			frappe.model.is_numeric_field(df) ? "text-right" : "",
		].join(" ");

		const html_map = {
			Subject: this.get_subject_html(doc),
			Field: field_html(),
		};
		let column_html = html_map[col.type];

		// listview_setting formatter
		if (this.settings.formatters && this.settings.formatters[fieldname]) {
			column_html = this.settings.formatters[fieldname](value, df, doc);
		}

		return `
			<div class="${css_class}">
				${column_html}
			</div>
		`;
	}

	get_tags_html(user_tags, limit, colored = false) {
		let get_tag_html = (tag) => {
			let color = "",
				style = "";
			if (tag) {
				if (colored) {
					color = frappe.get_palette(tag);
					style = `background-color: var(${color[0]}); color: var(${color[1]})`;
				}

				return `<div class="tag-pill ellipsis" title="${tag}" style="${style}">${tag}</div>`;
			}
		};
		return user_tags
			.split(",")
			.slice(1, limit + 1)
			.map(get_tag_html)
			.join("");
	}

	get_meta_html(doc) {
		let html = "";

		let settings_button = null;
		if (this.settings.button && this.settings.button.show(doc)) {
			settings_button = `
				<span class="list-actions">
					<button class="btn btn-action btn-default btn-xs"
						data-name="${doc.name}" data-idx="${doc._idx}"
						title="${this.settings.button.get_description(doc)}">
						${this.settings.button.get_label(doc)}
					</button>
				</span>
			`;
		}

		const modified = comment_when(doc.modified, true);

		let assigned_to = `<div class="list-assignments">
			<span class="avatar avatar-small">
			<span class="avatar-empty"></span>
		</div>`;

		let assigned_users = JSON.parse(doc._assign || "[]");
		if (assigned_users.length) {
			assigned_to = `<div class="list-assignments">
					${frappe.avatar_group(assigned_users, 3, { filterable: true })[0].outerHTML}
				</div>`;
		}

		const comment_count = `<span class="comment-count">
				${frappe.utils.icon("small-message")}
				${doc._comment_count > 99 ? "99+" : doc._comment_count || 0}
			</span>`;

		html += `
			<div class="level-item list-row-activity hidden-xs">
				<div class="hidden-md hidden-xs">
					${settings_button || assigned_to}
				</div>
				${modified}
				${comment_count}
			</div>
			<div class="level-item visible-xs text-right">
				${this.get_indicator_dot(doc)}
			</div>
		`;

		return html;
	}

	get_count_str() {
		let current_count = this.data.length;
		let count_without_children = this.data.uniqBy((d) => d.name).length;

		return frappe.db
			.count(this.doctype, {
				filters: this.get_filters_for_args(),
			})
			.then((total_count) => {
				this.total_count = total_count || current_count;
				this.count_without_children =
					count_without_children !== current_count ? count_without_children : undefined;
				let str = __("{0} of {1}", [current_count, this.total_count]);
				if (this.count_without_children) {
					str = __("{0} of {1} ({2} rows with children)", [
						count_without_children,
						this.total_count,
						current_count,
					]);
				}
				return str;
			});
	}

	get_form_link(doc) {
		if (this.settings.get_form_link) {
			return this.settings.get_form_link(doc);
		}

		return `/app/${frappe.router.slug(
			frappe.router.doctype_layout || this.doctype
		)}/${encodeURIComponent(cstr(doc.name))}`;
	}

	get_seen_class(doc) {
		return JSON.parse(doc._seen || "[]").includes(frappe.session.user) ? "" : "bold";
	}

	get_like_html(doc) {
		const liked_by = JSON.parse(doc._liked_by || "[]");
		let heart_class = liked_by.includes(frappe.session.user) ? "liked-by liked" : "not-liked";

		return `<span
			class="like-action ${heart_class}"
			data-name="${doc.name}" data-doctype="${this.doctype}"
			data-liked-by="${encodeURI(doc._liked_by) || "[]"}"
			title="${liked_by.map((u) => frappe.user_info(u).fullname).join(", ")}">
			${frappe.utils.icon("heart", "sm", "like-icon")}
		</span>
		<span class="likes-count">
			${liked_by.length > 99 ? __("99") + "+" : __(liked_by.length || "")}
		</span>`;
	}

	get_subject_html(doc) {
		let subject_field = this.columns[0].df;
		let value = doc[subject_field.fieldname];
		if (this.settings.formatters && this.settings.formatters[subject_field.fieldname]) {
			let formatter = this.settings.formatters[subject_field.fieldname];
			value = formatter(value, subject_field, doc);
		}
		if (!value) {
			value = doc.name;
		}
		let subject = strip_html(value.toString());
		let escaped_subject = frappe.utils.escape_html(subject);

		const seen = this.get_seen_class(doc);

		let subject_html = `
			<span class="level-item select-like">
				<input class="list-row-checkbox" type="checkbox"
					data-name="${escape(doc.name)}">
				<span class="list-row-like hidden-xs style="margin-bottom: 1px;">
					${this.get_like_html(doc)}
				</span>
			</span>
			<span class="level-item ${seen} ellipsis" title="${escaped_subject}">
				<a class="ellipsis"
					href="${this.get_form_link(doc)}"
					title="${escaped_subject}"
					data-doctype="${this.doctype}"
					data-name="${escaped_subject}">
					${subject}
				</a>
			</span>
		`;

		return subject_html;
	}

	get_indicator_html(doc, show_workflow_state) {
		const indicator = frappe.get_indicator(doc, this.doctype, show_workflow_state);
		// sequence is important
		const docstatus_description = [
			__("Document is in draft state"),
			__("Document has been submitted"),
			__("Document has been cancelled"),
		];
		const title = docstatus_description[doc.docstatus || 0];
		if (indicator) {
			return `<span class="indicator-pill ${indicator[1]} filterable ellipsis"
				data-filter='${indicator[2]}' title='${title}'>
				<span class="ellipsis"> ${__(indicator[0])}</span>
			</span>`;
		}
		return "";
	}

	get_indicator_dot(doc) {
		const indicator = frappe.get_indicator(doc, this.doctype);
		if (!indicator) return "";
		return `<span class='indicator ${indicator[1]}' title='${__(indicator[0])}'></span>`;
	}

	get_image_url(doc) {
		let url = doc.image ? doc.image : doc[this.meta.image_field];
		// absolute url for mobile
		if (window.cordova && !frappe.utils.is_url(url)) {
			url = frappe.base_url + url;
		}
		return url || null;
	}

	setup_events() {
		this.setup_filterable();
		this.setup_list_click();
		this.setup_drag_click();
		this.setup_tag_event();
		this.setup_new_doc_event();
		this.setup_check_events();
		this.setup_like();
		this.setup_realtime_updates();
		this.setup_action_handler();
		this.setup_keyboard_navigation();
	}

	setup_keyboard_navigation() {
		let focus_first_row = () => {
			this.$result.find(".list-row-container:first").focus();
		};
		let focus_next = () => {
			$(document.activeElement).next().focus();
		};
		let focus_prev = () => {
			$(document.activeElement).prev().focus();
		};
		let list_row_focused = () => {
			return $(document.activeElement).is(".list-row-container");
		};
		let check_row = ($row) => {
			let $input = $row.find("input[type=checkbox]");
			$input.click();
		};
		let get_list_row_if_focused = () =>
			list_row_focused() ? $(document.activeElement) : null;

		let is_current_page = () => this.page.wrapper.is(":visible");
		let is_input_focused = () => $(document.activeElement).is("input");

		let handle_navigation = (direction) => {
			if (!is_current_page() || is_input_focused()) return false;

			let $list_row = get_list_row_if_focused();
			if ($list_row) {
				direction === "down" ? focus_next() : focus_prev();
			} else {
				focus_first_row();
			}
		};

		frappe.ui.keys.add_shortcut({
			shortcut: "down",
			action: () => handle_navigation("down"),
			description: __("Navigate list down", null, "Description of a list view shortcut"),
			page: this.page,
		});

		frappe.ui.keys.add_shortcut({
			shortcut: "up",
			action: () => handle_navigation("up"),
			description: __("Navigate list up", null, "Description of a list view shortcut"),
			page: this.page,
		});

		frappe.ui.keys.add_shortcut({
			shortcut: "shift+down",
			action: () => {
				if (!is_current_page() || is_input_focused()) return false;
				let $list_row = get_list_row_if_focused();
				check_row($list_row);
				focus_next();
			},
			description: __(
				"Select multiple list items",
				null,
				"Description of a list view shortcut"
			),
			page: this.page,
		});

		frappe.ui.keys.add_shortcut({
			shortcut: "shift+up",
			action: () => {
				if (!is_current_page() || is_input_focused()) return false;
				let $list_row = get_list_row_if_focused();
				check_row($list_row);
				focus_prev();
			},
			description: __(
				"Select multiple list items",
				null,
				"Description of a list view shortcut"
			),
			page: this.page,
		});

		frappe.ui.keys.add_shortcut({
			shortcut: "enter",
			action: () => {
				let $list_row = get_list_row_if_focused();
				if ($list_row) {
					$list_row.find("a[data-name]")[0].click();
					return true;
				}
				return false;
			},
			description: __("Open list item", null, "Description of a list view shortcut"),
			page: this.page,
		});

		frappe.ui.keys.add_shortcut({
			shortcut: "space",
			action: () => {
				let $list_row = get_list_row_if_focused();
				if ($list_row) {
					check_row($list_row);
					return true;
				}
				return false;
			},
			description: __("Select list item", null, "Description of a list view shortcut"),
			page: this.page,
		});
	}

	setup_filterable() {
		// filterable events
		this.$result.on("click", ".filterable", (e) => {
			if (e.metaKey || e.ctrlKey) return;
			e.stopPropagation();
			const $this = $(e.currentTarget);
			const filters = $this.attr("data-filter").split("|");
			const filters_to_apply = filters.map((f) => {
				f = f.split(",");
				if (f[2] === "Today") {
					f[2] = frappe.datetime.get_today();
				} else if (f[2] == "User") {
					f[2] = frappe.session.user;
				}
				this.filter_area.remove(f[0]);
				return [this.doctype, f[0], f[1], f.slice(2).join(",")];
			});
			this.filter_area.add(filters_to_apply);
		});
	}

	setup_list_click() {
		this.$result.on("click", ".list-row, .image-view-header, .file-header", (e) => {
			const $target = $(e.target);
			// tick checkbox if Ctrl/Meta key is pressed
			if ((e.ctrlKey || e.metaKey) && !$target.is("a")) {
				const $list_row = $(e.currentTarget);
				const $check = $list_row.find(".list-row-checkbox");
				$check.prop("checked", !$check.prop("checked"));
				e.preventDefault();
				this.on_row_checked();
				return;
			}
			// don't open form when checkbox, like, filterable are clicked
			if (
				$target.hasClass("filterable") ||
				$target.hasClass("select-like") ||
				$target.hasClass("file-select") ||
				$target.hasClass("list-row-like") ||
				$target.is(":checkbox")
			) {
				e.stopPropagation();
				return;
			}

			// link, let the event be handled via set_route
			if ($target.is("a")) return;

			// clicked on the row, open form
			const $row = $(e.currentTarget);
			const link = $row.find(".list-subject a").get(0);
			if (link) {
				frappe.set_route(link.pathname);
				return false;
			}
		});
	}

	setup_drag_click() {
		/*
			Click on the check box in the list view and
			drag through the rows to select.

			Do it again to unselect.

			If the first click is on checked checkbox, then it will unselect rows on drag,
			else if it is unchecked checkbox, it will select rows on drag.
		*/
		this.dragClick = false;
		this.$result.on("mousedown", ".list-row-checkbox", (e) => {
			this.dragClick = true;
			this.check = !e.target.checked;
		});
		$(document).on("mouseup", () => {
			this.dragClick = false;
		});
		this.$result.on("mousemove", ".level.list-row", (e) => {
			if (this.dragClick) {
				this.check_row_on_drag(e, this.check);
			}
		});
	}

	check_row_on_drag(event, check = true) {
		$(event.target).find(".list-row-checkbox").prop("checked", check);
		this.on_row_checked();
	}

	setup_action_handler() {
		this.$result.on("click", ".btn-action", (e) => {
			const $button = $(e.currentTarget);
			const doc = this.data[$button.attr("data-idx")];
			this.settings.button.action(doc);
			e.stopPropagation();
			return false;
		});
	}

	setup_check_events() {
		this.$result.on("change", "input[type=checkbox]", (e) => {
			const $target = $(e.currentTarget);

			if ($target.is(".list-header-subject .list-check-all")) {
				const $check = this.$result.find(".checkbox-actions .list-check-all");
				$check.prop("checked", $target.prop("checked"));
				$check.trigger("change");
			} else if ($target.is(".checkbox-actions .list-check-all")) {
				const $check = this.$result.find(".list-header-subject .list-check-all");
				$check.prop("checked", $target.prop("checked"));

				this.$result.find(".list-row-checkbox").prop("checked", $target.prop("checked"));
			} else if ($target.attr("data-parent")) {
				this.$result
					.find(`.${$target.attr("data-parent")}`)
					.find(".list-row-checkbox")
					.prop("checked", $target.prop("checked"));
			}

			this.on_row_checked();
		});

		this.$result.on("click", ".list-row-checkbox", (e) => {
			const $target = $(e.currentTarget);

			// shift select checkboxes
			if (e.shiftKey && this.$checkbox_cursor && !$target.is(this.$checkbox_cursor)) {
				const name_1 = decodeURIComponent(this.$checkbox_cursor.data().name);
				const name_2 = decodeURIComponent($target.data().name);
				const index_1 = this.data.findIndex((d) => d.name === name_1);
				const index_2 = this.data.findIndex((d) => d.name === name_2);
				let [min_index, max_index] = [index_1, index_2];

				if (min_index > max_index) {
					[min_index, max_index] = [max_index, min_index];
				}

				let docnames = this.data.slice(min_index + 1, max_index).map((d) => d.name);
				const selector = docnames
					.map((name) => `.list-row-checkbox[data-name="${encodeURIComponent(name)}"]`)
					.join(",");
				this.$result.find(selector).prop("checked", true);
			}

			this.$checkbox_cursor = $target;

			this.update_checkbox($target);
		});

		let me = this;
		this.page.actions_btn_group.on("show.bs.dropdown", () => {
			me.toggle_workflow_actions();
		});
	}

	setup_like() {
		this.$result.on("click", ".like-action", frappe.ui.click_toggle_like);
		this.$result.on("click", ".list-liked-by-me", (e) => {
			const $this = $(e.currentTarget);
			$this.toggleClass("active");

			if ($this.hasClass("active")) {
				this.filter_area.add(
					this.doctype,
					"_liked_by",
					"like",
					"%" + frappe.session.user + "%"
				);
			} else {
				this.filter_area.remove("_liked_by");
			}
		});
	}

	setup_new_doc_event() {
		this.$no_result.find(".btn-new-doc").click(() => {
			if (this.settings.primary_action) {
				this.settings.primary_action();
			} else {
				this.make_new_doc();
			}
		});
	}

	setup_tag_event() {
		this.tags_shown = false;
		this.list_sidebar &&
			this.list_sidebar.parent.on("click", ".list-tag-preview", () => {
				this.tags_shown = !this.tags_shown;
				this.toggle_tags();
			});
	}

	setup_realtime_updates() {
		this.pending_document_refreshes = [];

		if (this.list_view_settings?.disable_auto_refresh || this.realtime_events_setup) {
			return;
		}
		frappe.socketio.doctype_subscribe(this.doctype);
		frappe.realtime.off("list_update");
		frappe.realtime.on("list_update", (data) => {
			if (data?.doctype !== this.doctype) {
				return;
			}

			// if some bulk operation is happening by selecting list items, don't refresh
			if (this.$checks && this.$checks.length) {
				return;
			}

			if (this.avoid_realtime_update()) {
				return;
			}

			this.pending_document_refreshes.push(data);
			this.debounced_refresh();
		});
		this.realtime_events_setup = true;
	}

	disable_realtime_updates() {
		frappe.socketio.doctype_unsubscribe(this.doctype);
		this.realtime_events_setup = false;
	}

	process_document_refreshes() {
		if (!this.pending_document_refreshes.length) return;

		const route = frappe.get_route() || [];
		if (!cur_list || route[0] != "List" || cur_list.doctype != route[1]) {
			// wait till user is back on list view before refreshing
			this.pending_document_refreshes = [];
			this.disable_realtime_updates();
			return;
		}

		const names = this.pending_document_refreshes.map((d) => d.name);
		this.pending_document_refreshes = this.pending_document_refreshes.filter(
			(d) => names.indexOf(d.name) === -1
		);

		if (!names.length) return;

		// filters to get only the doc with this name
		const call_args = this.get_call_args();
		call_args.args.filters.push([this.doctype, "name", "in", names]);
		call_args.args.start = 0;

		frappe.call(call_args).then(({ message }) => {
			if (!message) return;
			const data = frappe.utils.dict(message.keys, message.values);

			if (!(data && data.length)) {
				// this doc was changed and should not be visible
				// in the listview according to filters applied
				// let's remove it manually
				this.data = this.data.filter((d) => names.indexOf(d.name) === -1);
				this.render_list();
				return;
			}

			data.forEach((datum) => {
				const index = this.data.findIndex((doc) => doc.name === datum.name);

				if (index === -1) {
					// append new data
					this.data.push(datum);
				} else {
					// update this data in place
					this.data[index] = datum;
				}
			});

			this.data.sort((a, b) => {
				const a_value = a[this.sort_by] || "";
				const b_value = b[this.sort_by] || "";

				let return_value = 0;
				if (a_value > b_value) {
					return_value = 1;
				}

				if (b_value > a_value) {
					return_value = -1;
				}

				if (this.sort_order === "desc") {
					return_value = -return_value;
				}
				return return_value;
			});
			if (this.$checks && this.$checks.length) {
				this.set_rows_as_checked();
			}
			this.toggle_result_area();
			this.render_list();
		});
	}

	avoid_realtime_update() {
		if (this.filter_area.is_being_edited()) {
			return true;
		}
		// this is set when a bulk operation is called from a list view which might update the list view
		// this is to avoid the list view from refreshing a lot of times
		// the list view is updated once after the bulk operation is complete
		if (this.disable_list_update) {
			return true;
		}
		return false;
	}

	set_rows_as_checked() {
		$.each(this.$checks, (i, el) => {
			let docname = $(el).attr("data-name");
			this.$result.find(`.list-row-checkbox[data-name='${docname}']`).prop("checked", true);
		});
		this.on_row_checked();
	}

	on_row_checked() {
		this.$list_head_subject =
			this.$list_head_subject || this.$result.find("header .list-header-subject");
		this.$checkbox_actions =
			this.$checkbox_actions || this.$result.find("header .checkbox-actions");

		this.$checks = this.$result.find(".list-row-checkbox:checked");

		this.$list_head_subject.toggle(this.$checks.length === 0);
		this.$checkbox_actions.toggle(this.$checks.length > 0);

		if (this.$checks.length === 0) {
			this.$list_head_subject.find(".list-check-all").prop("checked", false);
		} else {
			this.$checkbox_actions
				.find(".list-header-meta")
				.html(__("{0} items selected", [this.$checks.length]));
			this.$checkbox_actions.show();
			this.$list_head_subject.hide();
		}
		this.update_checkbox();
		this.toggle_actions_menu_button(this.$checks.length > 0);
	}

	toggle_tags() {
		this.$result.find(".tag-col").toggleClass("hide");
		const preview_label = this.tags_shown ? __("Hide Tags") : __("Show Tags");
		this.list_sidebar.parent.find(".list-tag-preview").text(preview_label);
	}

	get_checked_items(only_docnames) {
		const docnames = Array.from(this.$checks || []).map((check) =>
			cstr(unescape($(check).data().name))
		);

		if (only_docnames) return docnames;

		return this.data.filter((d) => docnames.includes(d.name));
	}

	clear_checked_items() {
		this.$checks && this.$checks.prop("checked", false);
		this.on_row_checked();
	}

	save_view_user_settings(obj) {
		return frappe.model.user_settings.save(this.doctype, this.view_name, obj);
	}

	on_update() {}

	update_url_with_filters() {
		if (frappe.get_route_str() == this.page_name && !this.report_name) {
			// only update URL if the route still matches current page.
			// do not update if current list is a "saved report".
			window.history.replaceState(null, null, this.get_url_with_filters());
		}
	}

	get_url_with_filters() {
		const query_params = this.get_filters_for_args()
			.map((filter) => {
				if (filter[2] === "=") {
					return `${filter[1]}=${encodeURIComponent(filter[3])}`;
				}
				return [
					filter[1],
					"=",
					encodeURIComponent(JSON.stringify([filter[2], filter[3]])),
				].join("");
			})
			.join("&");

		let full_url = window.location.href.replace(window.location.search, "");
		if (query_params) {
			full_url += "?" + query_params;
		}
		return full_url;
	}

	get_menu_items() {
		const doctype = this.doctype;
		const items = [];

		if (frappe.model.can_import(doctype, null, this.meta)) {
			items.push({
				label: __("Import", null, "Button in list view menu"),
				action: () =>
					frappe.set_route("list", "data-import", {
						reference_doctype: doctype,
					}),
				standard: true,
			});
		}

		if (frappe.model.can_set_user_permissions(doctype)) {
			items.push({
				label: __("User Permissions", null, "Button in list view menu"),
				action: () =>
					frappe.set_route("list", "user-permission", {
						allow: doctype,
					}),
				standard: true,
			});
		}

		if (frappe.user_roles.includes("System Manager")) {
			items.push({
				label: __("Role Permissions Manager", null, "Button in list view menu"),
				action: () =>
					frappe.set_route("permission-manager", {
						doctype,
					}),
				standard: true,
			});
		}

		if (
			frappe.model.can_create("Custom Field") &&
			frappe.model.can_create("Property Setter")
		) {
			items.push({
				label: __("Customize", null, "Button in list view menu"),
				action: () => {
					if (!this.meta) return;
					if (this.meta.custom) {
						frappe.set_route("form", "doctype", doctype);
					} else if (!this.meta.custom) {
						frappe.set_route("form", "customize-form", {
							doc_type: doctype,
						});
					}
				},
				standard: true,
				shortcut: "Ctrl+J",
			});
		}

		items.push({
			label: __("Toggle Sidebar", null, "Button in list view menu"),
			action: () => this.toggle_side_bar(),
			condition: () => !this.hide_sidebar,
			standard: true,
			shortcut: "Ctrl+K",
		});

		if (frappe.user.has_role("System Manager") && frappe.boot.developer_mode === 1) {
			// edit doctype
			items.push({
				label: __("Edit DocType", null, "Button in list view menu"),
				action: () => frappe.set_route("form", "doctype", doctype),
				standard: true,
			});
		}

		if (frappe.user.has_role("System Manager")) {
			if (this.get_view_settings) {
				items.push(this.get_view_settings());
			}
		}

		return items;
	}

	get_view_settings() {
		return {
			label: __("List Settings", null, "Button in list view menu"),
			action: () => this.show_list_settings(),
			standard: true,
		};
	}

	show_list_settings() {
		frappe.model.with_doctype(this.doctype, () => {
			new ListSettings({
				listview: this,
				doctype: this.doctype,
				settings: this.list_view_settings,
				meta: frappe.get_meta(this.doctype),
			});
		});
	}

	get_workflow_action_menu_items() {
		const workflow_actions = [];
		const me = this;

		if (frappe.model.has_workflow(this.doctype)) {
			const actions = frappe.workflow.get_all_transition_actions(this.doctype);
			actions.forEach((action) => {
				workflow_actions.push({
					label: __(action),
					name: action,
					action: () => {
						me.disable_list_update = true;
						frappe
							.xcall("frappe.model.workflow.bulk_workflow_approval", {
								docnames: this.get_checked_items(true),
								doctype: this.doctype,
								action: action,
							})
							.finally(() => {
								me.disable_list_update = false;
							});
					},
					is_workflow_action: true,
				});
			});
		}
		return workflow_actions;
	}

	toggle_workflow_actions() {
		if (!frappe.model.has_workflow(this.doctype)) return;

		Object.keys(this.workflow_action_items).forEach((key) => {
			this.workflow_action_items[key].addClass("disabled");
		});
		const checked_items = this.get_checked_items();

		frappe
			.xcall("frappe.model.workflow.get_common_transition_actions", {
				docs: checked_items,
				doctype: this.doctype,
			})
			.then((actions) => {
				Object.keys(this.workflow_action_items).forEach((key) => {
					this.workflow_action_items[key].removeClass("disabled");
					this.workflow_action_items[key].toggle(actions.includes(key));
				});
			});
	}

	get_actions_menu_items() {
		const doctype = this.doctype;
		const actions_menu_items = [];
		const bulk_operations = new BulkOperations({ doctype: this.doctype });

		const is_field_editable = (field_doc) => {
			return (
				field_doc.fieldname &&
				frappe.model.is_value_type(field_doc) &&
				field_doc.fieldtype !== "Read Only" &&
				!field_doc.hidden &&
				!field_doc.read_only &&
				!field_doc.is_virtual
			);
		};

		const has_editable_fields = (doctype) => {
			return frappe.meta
				.get_docfields(doctype)
				.some((field_doc) => is_field_editable(field_doc));
		};

		const has_submit_permission = (doctype) => {
			return frappe.perm.has_perm(doctype, 0, "submit");
		};

		// utility
		const bulk_assignment = () => {
			return {
				label: __("Assign To", null, "Button in list view actions menu"),
				action: () => {
					this.disable_list_update = true;
					bulk_operations.assign(this.get_checked_items(true), () => {
						this.disable_list_update = false;
						this.clear_checked_items();
						this.refresh();
					});
				},
				standard: true,
			};
		};

		const bulk_assignment_rule = () => {
			return {
				label: __("Apply Assignment Rule", null, "Button in list view actions menu"),
				action: () => {
					this.disable_list_update = true;
					bulk_operations.apply_assignment_rule(this.get_checked_items(true), () => {
						this.disable_list_update = false;
						this.clear_checked_items();
						this.refresh();
					});
				},
				standard: true,
			};
		};

		const bulk_add_tags = () => {
			return {
				label: __("Add Tags", null, "Button in list view actions menu"),
				action: () => {
					this.disable_list_update = true;
					bulk_operations.add_tags(this.get_checked_items(true), () => {
						this.disable_list_update = false;
						this.clear_checked_items();
						this.refresh();
					});
				},
				standard: true,
			};
		};

		const bulk_printing = () => {
			return {
				label: __("Print", null, "Button in list view actions menu"),
				action: () => bulk_operations.print(this.get_checked_items()),
				standard: true,
			};
		};

		const bulk_delete = () => {
			return {
				label: __("Delete", null, "Button in list view actions menu"),
				action: () => {
					const docnames = this.get_checked_items(true).map((docname) =>
						docname.toString()
					);
					let message = __(
						"Delete {0} item permanently?",
						[docnames.length],
						"Title of confirmation dialog"
					);
					if (docnames.length > 1) {
						message = __(
							"Delete {0} items permanently?",
							[docnames.length],
							"Title of confirmation dialog"
						);
					}
					frappe.confirm(message, () => {
						this.disable_list_update = true;
						bulk_operations.delete(docnames, () => {
							this.disable_list_update = false;
							this.clear_checked_items();
							this.refresh();
						});
					});
				},
				standard: true,
			};
		};

		const bulk_cancel = () => {
			return {
				label: __("Cancel", null, "Button in list view actions menu"),
				action: () => {
					const docnames = this.get_checked_items(true);
					if (docnames.length > 0) {
						frappe.confirm(
							__(
								"Cancel {0} documents?",
								[docnames.length],
								"Title of confirmation dialog"
							),
							() => {
								this.disable_list_update = true;
								bulk_operations.submit_or_cancel(docnames, "cancel", () => {
									this.disable_list_update = false;
									this.clear_checked_items();
									this.refresh();
								});
							}
						);
					}
				},
				standard: true,
			};
		};

		const bulk_submit = () => {
			return {
				label: __("Submit", null, "Button in list view actions menu"),
				action: () => {
					const docnames = this.get_checked_items(true);
					if (docnames.length > 0) {
						frappe.confirm(
							__(
								"Submit {0} documents?",
								[docnames.length],
								"Title of confirmation dialog"
							),
							() => {
								this.disable_list_update = true;
								bulk_operations.submit_or_cancel(docnames, "submit", () => {
									this.disable_list_update = false;
									this.clear_checked_items();
									this.refresh();
								});
							}
						);
					}
				},
				standard: true,
			};
		};

		const bulk_edit = () => {
			return {
				label: __("Edit", null, "Button in list view actions menu"),
				action: () => {
					let field_mappings = {};

					frappe.meta.get_docfields(doctype).forEach((field_doc) => {
						if (is_field_editable(field_doc)) {
							field_mappings[field_doc.label] = Object.assign({}, field_doc);
						}
					});

					this.disable_list_update = true;
					bulk_operations.edit(this.get_checked_items(true), field_mappings, () => {
						this.disable_list_update = false;
						this.refresh();
					});
				},
				standard: true,
			};
		};

		const bulk_export = () => {
			return {
				label: __("Export", null, "Button in list view actions menu"),
				action: () => {
					const docnames = this.get_checked_items(true);

					bulk_operations.export(doctype, docnames);
				},
				standard: true,
			};
		};

		// bulk edit
		if (has_editable_fields(doctype)) {
			actions_menu_items.push(bulk_edit());
		}

		actions_menu_items.push(bulk_export());

		// bulk assignment
		actions_menu_items.push(bulk_assignment());

		actions_menu_items.push(bulk_assignment_rule());

		actions_menu_items.push(bulk_add_tags());

		// bulk printing
		if (frappe.model.can_print(doctype)) {
			actions_menu_items.push(bulk_printing());
		}

		// bulk submit
		if (
			frappe.model.is_submittable(doctype) &&
			has_submit_permission(doctype) &&
			!frappe.model.has_workflow(doctype)
		) {
			actions_menu_items.push(bulk_submit());
		}

		// bulk cancel
		if (frappe.model.can_cancel(doctype) && !frappe.model.has_workflow(doctype)) {
			actions_menu_items.push(bulk_cancel());
		}

		// bulk delete
		if (frappe.model.can_delete(doctype)) {
			actions_menu_items.push(bulk_delete());
		}

		return actions_menu_items;
	}

	parse_filters_from_route_options() {
		const filters = [];

		for (let field in frappe.route_options) {
			let doctype = null;
			let value = frappe.route_options[field];

			let value_array;
			if ($.isArray(value) && value[0].startsWith("[") && value[0].endsWith("]")) {
				value_array = [];
				for (var i = 0; i < value.length; i++) {
					value_array.push(JSON.parse(value[i]));
				}
			} else if (typeof value === "string" && value.startsWith("[") && value.endsWith("]")) {
				value = JSON.parse(value);
			}

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
				doctype = frappe.meta.get_doctype_for_field(this.doctype, field);
			}

			if (doctype) {
				if (value_array) {
					for (var j = 0; j < value_array.length; j++) {
						if ($.isArray(value_array[j])) {
							filters.push([doctype, field, value_array[j][0], value_array[j][1]]);
						} else {
							filters.push([doctype, field, "=", value_array[j]]);
						}
					}
				} else if ($.isArray(value)) {
					filters.push([doctype, field, value[0], value[1]]);
				} else {
					filters.push([doctype, field, "=", value]);
				}
			}
		}

		return filters;
	}
};

frappe.get_list_view = (doctype) => {
	let route = `List/${doctype}/List`;
	return frappe.views.list_view[route];
};
