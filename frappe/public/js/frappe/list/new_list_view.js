frappe.provide('frappe.views');

frappe.views.ListView = class ListView {
	constructor(opts) {
		Object.assign(this, opts);

		// load last view
		const re_route = this.build_route();
		this.view = this.route[2];
		if (re_route) {
			frappe.set_route(this.route);
			this.constructor(opts);
			return;
		}

		this.setup_defaults();

		// make view
		this.setup_page();
		this.setup_page_head();
		this.setup_side_bar();
		this.setup_main_section();

		this.refresh = frappe.utils.throttle(this.refresh, 1000);
		this.refresh();

		new_cur_list = this;
	}

	build_route() {
		//TODO: remember to load last kanban board and last email inbox from user_settings
		this.route = frappe.get_route();
		const user_settings = frappe.get_user_settings(this.doctype);

		if (this.route.length === 2) {
			// routed to List/{doctype}
			//   -> route to last_view [OR]
			//   -> route to List/{doctype}/List
			const last_view = frappe.views.is_valid(user_settings.last_view)
				&& user_settings.last_view;

			this.route.push(last_view || 'List');
			return true;
		} else {
			return false;
		}
	}

	setup_defaults() {
		this.page_name = 'List/' + this.doctype;
		this.page_title = this.page_title || __(this.doctype);
		this.meta = frappe.get_meta(this.doctype);
		this.settings = frappe.listview_settings[this.doctype];
		this.user_settings = frappe.get_user_settings(this.doctype);

		this.start = 0;
		this.page_length = 20;
		this.data = [];
		this.method = 'frappe.desk.reportview.get';

		this.default_fields = [
			'name',
			'owner',
			'docstatus',
			'_user_tags',
			'_comments',
			'modified',
			'modified_by',
			'_assign',
			'_liked_by',
			'_seen',
			'enabled',
			'disabled',
			this.meta.title_field,
			this.meta.image_field
		];

		this.set_stats();
		this.list_fields = new ListFields(this);
	}

	set_stats() {
		this.stats = ['_user_tags'];
		// add workflow field (as priority)
		this.workflow_state_fieldname = frappe.workflow.get_state_fieldname(this.doctype);
		if (this.workflow_state_fieldname) {
			if (!frappe.workflow.workflows[this.doctype]['override_status']) {
				this._add_field(this.workflow_state_fieldname);
			}
			this.stats.push(this.workflow_state_fieldname);
		}
	}

	setup_page() {
		this.page = this.parent.page;
		this.$page = $(this.parent);
		this.page.page_form.removeClass('row').addClass('flex');
	}

	setup_page_head() {
		this.page.set_title(this.page_title);
		this.menu = new ListMenu(this);
	}

	setup_side_bar() {
		this.list_sidebar = new frappe.views.ListSidebar({
			doctype: this.doctype,
			stats: this.stats,
			parent: this.$page.find('.layout-side-section'),
			// set_filter: this.set_filter.bind(this),
			default_filters: this.filters,
			page: this.page,
			list_view: this
		});
	}

	setup_main_section() {
		this.setup_list_wrapper();
		this.setup_filters();
		this.setup_sort_selector();
		this.setup_result_area();
	}

	setup_list_wrapper() {
		this.$frappe_list = $('<div class="frappe-list">').appendTo(this.page.main);
	}

	setup_filters() {
		this.filter_area = new FilterArea(this);
	}

	setup_sort_selector() {
		this.sort_selector = new frappe.ui.SortSelector({
			parent: this.filter_area.$filter_list_wrapper,
			doctype: this.doctype,
			args: 'modified desc',
			change: () => this.list_view.refresh(true)
		});
	}

	setup_result_area() {
		this.$result = $(`<div class="result"></div>`).hide();
		this.$no_result = $(`<div class="no-result"></div>`).hide();

		this.$frappe_list.append(this.$result);
		this.$frappe_list.append(this.$no_result);
	}

	get_args() {
		return {
			doctype: this.doctype,
			fields: this.list_fields.get(),
			filters: this.filter_area.get(),
			order_by: this.sort_selector.get_sql_string(),
			with_comment_count: true,
			start: this.start,
			page_length: this.page_length
		};
	}

	refresh() {
		const args = this.get_args();
		console.log(args);

		return frappe.call({
			method: this.method,
			type: 'GET',
			args: args
		})
		.then(r => {
			this.update_data(r);
			this.render();
		});
	}

	update_data(r) {
		let data = r.message;
		data = frappe.utils.dict(data.keys, data.values);

		if (this.start === 0) {
			this.data = data;
		} else {
			this.data.concat(data);
		}
	}

	render() {
		if (this.data.length > 0) {
			this.$result.show();
			this.$no_result.hide();
			this.render_header();
			this.render_results();
		} else {
			this.$result.hide()
			this.$no_result.show();
		}
	}

	render_header() {
		const $header = $(`<div></div>`)
		this.$result.append($header);
	}

	render_results() {
		const $list = $('<div></div>')
		this.data.map(d => {
			$list.append(`<div>${d.name}</div>`);
		});
		this.$result.append($list);
	}
}

class ListFields {
	constructor(list_view) {
		this.list_view = list_view;
		this.meta = this.list_view.meta;
		this.doctype = list_view.doctype;
		this.set_fields();
	}

	get() {
		return this.fields;
	}

	set_fields() {
		if (this.list_view.user_settings.fields) {
			this._fields = this.list_view.user_settings.fields;
			this.build_fields();
			return;
		}

		this._fields = [];
		const add_field = f => this._add_field(f);

		// default fields
		this.list_view.default_fields.map(add_field);

		// fields in_list_view or in_standard_filter
		const fields = this.meta.fields.filter(df => {
			return (df.in_list_view || df.in_standard_filter)
				&& frappe.perm.has_perm(this.doctype, df.permlevel, 'read')
				&& !frappe.model.no_value_type.includes(df.fieldtype)
				&& !df.report_hide
		});

		fields.map(add_field);

		// currency fields
		fields.filter(
			df => df.fieldtype === 'Currency' && df.options
		).map(df => {
			if (df.options.includes(':')) {
				add_field(df.options.split(':')[1]);
			} else {
				add_field(df.options);
			}
		});

		// image fields
		const image_fields = fields.filter(
			df => df.fieldtype === 'Image'
		).map(df => {
			if (df.options) {
				add_field(df.options);
			} else {
				add_field(df.fieldname);
			}
		});

		// fields in listview_settings
		this.list_view.settings.add_fields.map(add_field);
		this.build_fields();
	}

	build_fields() {
		//de-dup
		this._fields = this._fields.uniqBy(f => f[0] + f[1]);
		// build this.fields
		this.fields = this._fields.map(f => frappe.model.get_full_column_name(f[0], f[1]));
		// save in user_settings
		frappe.model.user_settings.save(this.doctype, this.view, {
			fields: this._fields
		});
	}

	_add_field(fieldname) {
		if (!fieldname) return;
		let doctype = this.doctype;
		if (!frappe.model.std_fields_list.includes(fieldname) &&
			!frappe.meta.has_field(this.doctype, fieldname)) return;

		if (typeof fieldname === 'object') {
			// df is passed
			const df = fieldname;
			fieldname = df.fieldname;
			doctype = df.parent;
		}

		this._fields.push([fieldname, doctype]);
	}
}

class FilterArea {
	constructor(list_view) {
		this.list_view = list_view;
		this.standard_filters_wrapper = this.list_view.page.page_form;
		this.$filter_list_wrapper = $('<div class="filter-list">').appendTo(this.list_view.$frappe_list);
		this.setup();
	}

	setup() {
		this.make_standard_filters();
		this.make_filter_list();
	}

	get() {
		let filters = this.filter_list.get_filters();
		let standard_filters = this.get_standard_filters();

		return filters
			.concat(standard_filters)
			.uniqBy(JSON.stringify);
	}

	make_standard_filters() {
		$(
			`<div class="flex justify-center align-center">
				<span class="octicon octicon-search text-muted small"></span>
			</div>`
		)
			.css({
				height: '30px',
				width: '20px',
				marginRight: '-2px',
				marginLeft: '10px'
			})
			.prependTo(this.standard_filters_wrapper);

		let fields = [
			{
				fieldtype: 'Data',
				label: 'ID',
				condition: 'like',
				fieldname: 'name',
				onchange: () => this.list_view.refresh(true)
			}
		];

		const doctype_fields = this.list_view.meta.fields;

		fields = fields.concat(doctype_fields.filter(
			df => df.in_standard_filter &&
				!frappe.model.no_value_type.includes(df.fieldtype)
		).map(df => {
			let options = df.options;
			let condition = '=';
			let fieldtype = df.fieldtype;
			if (['Text', 'Small Text', 'Text Editor', 'Data'].includes(fieldtype)) {
				fieldtype = 'Data';
				condition = 'like';
			}
			if (df.fieldtype == "Select" && df.options) {
				options = df.options.split("\n");
				if (options.length > 0 && options[0] != "") {
					options.unshift("");
					options = options.join("\n");
				}
			}
			return {
				fieldtype: fieldtype,
				label: __(df.label),
				options: options,
				fieldname: df.fieldname,
				condition: condition,
				onchange: () => this.list_view.refresh(true)
			};
		}));

		if (fields.length > 3) {
			fields = fields.map((df, i) => {
				if (i >= 3) {
					df.input_class = 'hidden-sm hidden-xs';
				}
				return df;
			});
		}

		fields.map(df => this.list_view.page.add_field(df));
	}

	get_standard_filters() {
		const filters = [];
		const fields_dict = this.list_view.page.fields_dict;
		for (let key in fields_dict) {
			let field = fields_dict[key];
			let value = field.get_value();
			if (value) {
				if (field.df.condition === 'like' && !value.includes('%')) {
					value = '%' + value + '%';
				}
				filters.push([
					this.list_view.doctype,
					field.df.fieldname,
					field.df.condition || '=',
					value
				]);
			}
		}

		return filters;
	}

	make_filter_list() {
		this.filter_list = new frappe.ui.FilterList({
			base_list: this.list_view,
			parent: this.$filter_list_wrapper,
			doctype: this.list_view.doctype,
			default_filters: []
		});
	}
}

class ListMenu {
	constructor(list_view) {
		this.list_view = list_view;
		this.doctype = this.list_view.doctype;
		this.page = this.list_view.page;
		this.setup();
	}

	setup() {
		const doctype = this.doctype;
		// Refresh button for large screens
		this.page.set_secondary_action(__('Refresh'), () => {
			this.list_view.refresh(true);
		}, 'octicon octicon-sync').addClass('hidden-xs');

		// Refresh button as menu item in small screens
		this.page.add_menu_item(__('Refresh'), () => {
			this.list_view.refresh(true);
		}, 'octicon octicon-sync').addClass('visible-xs');

		if (frappe.model.can_import(doctype)) {
			this.page.add_menu_item(__('Import'), () => {
				frappe.set_route('data-import-tool', { doctype });
			}, true);
		}
		if (frappe.model.can_set_user_permissions(doctype)) {
			this.page.add_menu_item(__('User Permissions'), () => {
				frappe.set_route('List', 'User Permission', { allow: doctype });
			}, true);
		}
		if (frappe.user_roles.includes('System Manager')) {
			this.page.add_menu_item(__('Role Permissions Manager'), () => {
				frappe.set_route('permission-manager', { doctype });
			}, true);
			this.page.add_menu_item(__('Customize'), () => {
				frappe.set_route('Form', 'Customize Form', { doc_type: doctype });
			}, true);
		}

		this.make_bulk_assignment();
		if (frappe.model.can_print(doctype)) {
			this.make_bulk_printing();
		}

		// add to desktop
		this.page.add_menu_item(__('Add to Desktop'), () => {
			frappe.add_to_desktop(doctype, doctype);
		}, true);

		if (frappe.user.has_role('System Manager') && frappe.boot.developer_mode === 1) {
			// edit doctype
			this.page.add_menu_item(__('Edit DocType'), () => {
				frappe.set_route('Form', 'DocType', doctype);
			}, true);
		}
	}

	make_bulk_assignment() {
		// bulk assignment
		this.page.add_menu_item(__('Assign To'), () => {
			const docnames = this.list_view.get_checked_items().map(doc => doc.name);

			if (docnames.length > 0) {
				const dialog = new frappe.ui.form.AssignToDialog({
					obj: this.list_view,
					method: 'frappe.desk.form.assign_to.add_multiple',
					doctype: this.doctype,
					docname: docnames,
					bulk_assign: true,
					re_assign: true,
					callback: () => this.list_view.refresh(true)
				});
				dialog.clear();
				dialog.show();
			}
			else {
				frappe.msgprint(__('Select records for assignment'))
			}
		}, true);

	}

	make_bulk_printing() {
		const print_settings = frappe.model.get_doc(':Print Settings', 'Print Settings');
		const allow_print_for_draft = cint(print_settings.allow_print_for_draft);
		const is_submittable = frappe.model.is_submittable(this.doctype);
		const allow_print_for_cancelled = cint(print_settings.allow_print_for_cancelled);

		this.page.add_menu_item(__('Print'), () => {
			const items = this.list_view.get_checked_items();

			const valid_docs = items.filter(doc => {
				return !is_submittable || doc.docstatus === 1 ||
					(allow_print_for_cancelled && doc.docstatus == 2) ||
					(allow_print_for_draft && doc.docstatus == 0) ||
					frappe.user.has_role('Administrator')
			}).map(doc => doc.name);

			var invalid_docs = items.filter(doc => !valid_docs.includes(doc.name));

			if (invalid_docs.length > 0) {
				frappe.msgprint(__('You selected Draft or Cancelled documents'));
				return;
			}

			if (valid_docs.length > 0) {
				const dialog = new frappe.ui.Dialog({
					title: __('Print Documents'),
					fields: [
						{ 'fieldtype': 'Check', 'label': __('With Letterhead'), 'fieldname': 'with_letterhead' },
						{ 'fieldtype': 'Select', 'label': __('Print Format'), 'fieldname': 'print_sel', options: frappe.meta.get_print_formats(this.doctype) },
					]
				});

				dialog.set_primary_action(__('Print'), args => {
					if (!args) return;
					const default_print_format = frappe.get_meta(this.doctype).default_print_format;
					const with_letterhead = args.with_letterhead ? 1 : 0;
					const print_format = args.print_sel ? args.print_sel : default_print_format;
					const json_string = JSON.stringify(valid_docs);

					const w = window.open('/api/method/frappe.utils.print_format.download_multi_pdf?'
						+ 'doctype=' + encodeURIComponent(this.doctype)
						+ '&name=' + encodeURIComponent(json_string)
						+ '&format=' + encodeURIComponent(print_format)
						+ '&no_letterhead=' + (with_letterhead ? '0' : '1'));
					if (!w) {
						frappe.msgprint(__('Please enable pop-ups')); return;
					}
				});

				dialog.show();
			}
			else {
				frappe.msgprint(__('Select atleast 1 record for printing'))
			}
		}, true);
	}
}

// utility function to validate view modes
frappe.views.view_modes = ['List', 'Gantt', 'Kanban', 'Calendar', 'Image', 'Inbox', 'Report'];
frappe.views.is_valid = view_mode => frappe.views.view_modes.includes(view_mode);
