import BulkOperations from "./bulk_operations";

frappe.provide('frappe.views');

frappe.views.ListView = class ListView extends frappe.views.BaseList {
	static load_last_view() {
		const route = frappe.get_route();
		const doctype = route[1];

		if (route.length === 2) {
			// List/{doctype} => List/{doctype}/{last_view} or List
			const user_settings = frappe.get_user_settings(doctype);
			const last_view = user_settings.last_view;
			frappe.set_route('List', doctype, frappe.views.is_valid(last_view) ? last_view : 'List');
			return true;
		}
		return false;
	}

	constructor(opts) {
		super(opts);
		this.show();
	}

	has_permissions() {
		const can_read = frappe.perm.has_perm(this.doctype, 0, 'read');
		return can_read;
	}

	show() {
		if (!this.has_permissions()) {
			frappe.set_route('');
			frappe.msgprint(__(`Not permitted to view ${this.doctype}`));
			return;
		}

		super.show();
	}

	get view_name() {
		return 'List';
	}

	get view_user_settings() {
		return this.user_settings[this.view_name] || {};
	}

	setup_defaults() {
		super.setup_defaults();

		// initialize with saved order by
		this.sort_by = this.view_user_settings.sort_by || 'modified';
		this.sort_order = this.view_user_settings.sort_order || 'desc';

		// set filters from user_settings or list_settings
		if (this.view_user_settings.filters && this.view_user_settings.filters.length) {
			// Priority 1: user_settings
			const saved_filters = this.view_user_settings.filters;
			this.filters = this.validate_filters(saved_filters);
		} else {
			// Priority 2: filters in listview_settings
			this.filters = (this.settings.filters || []).map(f => {
				if (f.length === 3) {
					f = [this.doctype, f[0], f[1], f[2]];
				}
				return f;
			});
		}

		// build menu items
		this.menu_items = this.menu_items.concat(this.get_menu_items());

		this.actions_menu_items = this.get_actions_menu_items();

		this.patch_refresh_and_load_lib();
	}

	on_sort_change(sort_by, sort_order) {
		this.sort_by = sort_by;
		this.sort_order = sort_order;
		super.on_sort_change();
	}

	validate_filters(filters) {
		const valid_fields = this.meta.fields.map(df => df.fieldname);
		return filters
			.filter(f => valid_fields.includes(f[1]))
			.uniqBy(f => f[1]);
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
		this.actions_menu_items.map(item => {
			const $item = this.page.add_actions_menu_item(item.label, item.action, item.standard);
			if (item.class) {
				$item.addClass(item.class);
			}
		});
	}

	show_restricted_list_indicator_if_applicable() {
		const match_rules_list = frappe.perm.get_match_rules(this.doctype);
		if(match_rules_list.length) {
			this.restricted_list = $('<button class="restricted-list form-group">Restricted</button>')
				.prepend('<span class="octicon octicon-lock"></span>')
				.click(() => this.show_restrictions(match_rules_list))
				.appendTo(this.page.page_form);
		}
	}

	show_restrictions(match_rules_list=[]) {
		frappe.msgprint(frappe.render_template('list_view_permission_restrictions', {
			condition_list: match_rules_list
		}), 'Restrictions');
	}

	set_fields() {
		let fields = [].concat(
			frappe.model.std_fields_list,
			this.get_fields_in_list_view(),
			[this.meta.title_field, this.meta.image_field],
			(this.settings.add_fields || []),
			this.meta.track_seen ? '_seen' : null,
			this.sort_by,
			'enabled',
			'disabled'
		);

		fields.forEach(f => this._add_field(f));
	}

	patch_refresh_and_load_lib() {
		// throttle refresh for 1s
		this.refresh = this.refresh.bind(this);
		this.refresh = frappe.utils.throttle(this.refresh, 1000);
		this.load_lib = new Promise(resolve => {
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
		if (this.can_create) {
			this.page.set_primary_action(__('New'), () => {
				if (this.settings.primary_action) {
					this.settings.primary_action();
				} else {
					this.make_new_doc();
				}
			}, 'octicon octicon-plus');
		} else {
			this.page.clear_primary_action();
		}
	}

	make_new_doc() {
		const doctype = this.doctype;
		const options = {};
		this.filter_area.get().forEach(f => {
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

	setup_freeze_area() {
		this.$freeze =
			$(`<div class="freeze flex justify-center align-center text-muted">${__('Loading')}...</div>`)
				.hide();
		this.$result.append(this.$freeze);
	}

	setup_columns() {
		// setup columns for list view
		this.columns = [];

		const get_df = frappe.meta.get_docfield.bind(null, this.doctype);

		// 1st column: title_field or name
		if (this.meta.title_field) {
			this.columns.push({
				type: 'Subject',
				df: get_df(this.meta.title_field)
			});
		} else {
			this.columns.push({
				type: 'Subject',
				df: {
					label: __('Name'),
					fieldname: 'name'
				}
			});
		}

		// 2nd column: Status indicator
		if (frappe.has_indicator(this.doctype)) {
			// indicator
			this.columns.push({
				type: 'Status'
			});
		}

		const fields_in_list_view = this.get_fields_in_list_view();
		// Add rest from in_list_view docfields
		this.columns = this.columns.concat(
			fields_in_list_view
				.filter(df => {
					if (frappe.has_indicator(this.doctype) && df.fieldname === 'status') {
						return false;
					}
					if (!df.in_list_view) {
						return false;
					}
					return df.fieldname !== this.meta.title_field;
				})
				.map(df => ({
					type: 'Field',
					df
				}))
		);

		// limit to 4 columns
		this.columns = this.columns.slice(0, 4);
	}

	get_no_result_message() {
		const new_button = this.can_create ?
			`<p><button class="btn btn-primary btn-sm btn-new-doc">
				${__('Make a new {0}', [__(this.doctype)])}
			</button></p>` : '';

		return `<div class="msg-box no-border">
			<p>${__('No {0} found', [__(this.doctype)])}</p>
			${new_button}
		</div>`;
	}

	freeze() {
		this.$result.find('.list-count').html(`<span>${__('Refreshing')}...</span>`);
	}

	get_args() {
		const args = super.get_args();

		return Object.assign(args, {
			with_comment_count: true
		});
	}

	before_refresh() {
		if (frappe.route_options) {
			this.filters = this.parse_filters_from_route_options();

			return this.filter_area.clear(false)
				.then(() => this.filter_area.set(this.filters));
		}

		return Promise.resolve();
	}

	parse_filters_from_settings() {
		return (this.settings.filters || []).map(f => {
			if (f.length === 3) {
				f = [this.doctype, f[0], f[1], f[2]];
			}
			return f;
		});
	}

	toggle_result_area() {
		super.toggle_result_area();
		this.toggle_actions_menu_button(
			this.$result.find('.list-row-check:checked').length > 0
		);
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

	render_header() {
		if (this.$result.find('.list-row-head').length === 0) {
			// append header once
			this.$result.prepend(this.get_header_html());
		}
	}

	render_skeleton() {
		const $row = this.get_list_row_html_skeleton('<div><input type="checkbox" /></div>');
		this.$result.append($row);
	}

	before_render() {
		this.settings.before_render && this.settings.before_render();
		frappe.model.user_settings.save(this.doctype, 'last_view', this.view_name);
		this.save_view_user_settings({
			filters: this.filter_area.get(),
			sort_by: this.sort_selector.sort_by,
			sort_order: this.sort_selector.sort_order
		});
	}

	render() {
		this.$result.find('.list-row-container').remove();
		if (this.data.length > 0) {
			// append rows
			this.$result.append(
				this.data.map(doc => this.get_list_row_html(doc)).join('')
			);
		}
		this.on_row_checked();
		this.render_count();
		this.render_tags();
	}

	render_count() {
		this.get_count_str()
			.then(str => {
				this.$result.find('.list-count').html(`<span>${str}</span>`);
			});
	}

	render_tags() {
		const $list_rows = this.$result.find('.list-row-container');

		this.data.forEach((d, i) => {
			let tag_html = $(`<div class='tag-row'>
				<div class='list-tag hidden-xs'></div>
			</div>`).appendTo($list_rows.get(i));

			// add tags
			let tag_editor = new frappe.ui.TagEditor({
				parent: tag_html.find('.list-tag'),
				frm: {
					doctype: this.doctype,
					docname: d.name
				},
				list_sidebar: this.list_sidebar,
				user_tags: d._user_tags,
				on_change: (user_tags) => {
					d._user_tags = user_tags;
				}
			});

			tag_editor.wrapper.on('click', '.tagit-label', (e) => {
				const $this = $(e.currentTarget);
				this.filter_area.add(this.doctype, '_user_tags', '=', $this.text());
			});
		});
	}

	get_header_html() {
		const subject_field = this.columns[0].df;
		let subject_html = `
			<input class="level-item list-check-all hidden-xs" type="checkbox" title="${__("Select All")}">
			<span class="level-item list-liked-by-me">
				<i class="octicon octicon-heart text-extra-muted" title="${__("Likes")}"></i>
			</span>
			<span class="level-item">${__(subject_field.label)}</span>
		`;
		const $columns = this.columns.map(col => {
			let classes = [
				'list-row-col ellipsis',
				col.type == 'Subject' ? 'list-subject level' : 'hidden-xs',
				frappe.model.is_numeric_field(col.df) ? 'text-right' : ''
			].join(' ');

			return `
				<div class="${classes}">
					${col.type === 'Subject' ? subject_html : `
					<span>${__(col.df && col.df.label || col.type)}</span>`}
				</div>
			`;
		}).join('');

		return this.get_header_html_skeleton($columns, '<span class="list-count"></span>');
	}

	get_header_html_skeleton(left = '', right = '') {
		return `
			<header class="level list-row list-row-head text-muted small">
				<div class="level-left list-header-subject">
					${left}
				</div>
				<div class="level-left checkbox-actions">
					<div class="level list-subject">
						<input class="level-item list-check-all hidden-xs" type="checkbox" title="${__("Select All")}">
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
		return this.columns.map(col => this.get_column_html(col, doc)).join('');
	}

	get_right_html(doc) {
		return this.get_meta_html(doc);
	}

	get_list_row_html(doc) {
		return this.get_list_row_html_skeleton(this.get_left_html(doc), this.get_right_html(doc));
	}

	get_list_row_html_skeleton(left = '', right = '') {
		return `
			<div class="list-row-container">
				<div class="level list-row small">
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
		if (col.type === 'Status') {
			return `
				<div class="list-row-col hidden-xs ellipsis">
					${this.get_indicator_html(doc)}
				</div>
			`;
		}

		const df = col.df || {};
		const label = df.label;
		const fieldname = df.fieldname;
		const value = doc[fieldname] || '';

		// listview_setting formatter
		const formatters = this.settings.formatters;

		const format = () => {
			if (formatters && formatters[fieldname]) {
				return formatters[fieldname](value, df, doc);
			} else if (df.fieldtype === 'Code') {
				return value;
			} else {
				return frappe.format(value, df, null, doc);
			}
		};

		const field_html = () => {
			let html;
			const _value = typeof value === 'string' ? frappe.utils.escape_html(value) : value;

			if (df.fieldtype === 'Image') {
				html = df.options ?
					`<img src="${doc[df.options]}" style="max-height: 30px; max-width: 100%;">` :
					`<div class="missing-image small">
						<span class="octicon octicon-circle-slash"></span>
					</div>`;
			} else if (df.fieldtype === 'Select') {
				html = `<span class="filterable indicator ${frappe.utils.guess_colour(_value)} ellipsis"
					data-filter="${fieldname},=,${value}">
					${__(_value)}
				</span>`;
			} else if (df.fieldtype === 'Link') {
				html = `<a class="filterable text-muted ellipsis"
					data-filter="${fieldname},=,${value}">
					${_value}
				</a>`;
			} else if (df.fieldtype === 'Text Editor') {
				html = `<span class="text-muted ellipsis">
					${_value}
				</span>`;
			} else {
				html = `<a class="filterable text-muted ellipsis"
					data-filter="${fieldname},=,${value}">
					${format()}
				</a>`;
			}

			return `<span class="ellipsis"
				title="${__(label) + ': ' + _value}">
				${html}
			</span>`;
		};

		const class_map = {
			Subject: 'list-subject level',
			Field: 'hidden-xs'
		};
		const css_class = [
			'list-row-col ellipsis',
			class_map[col.type],
			frappe.model.is_numeric_field(df) ? 'text-right' : ''
		].join(' ');

		const html_map = {
			Subject: this.get_subject_html(doc),
			Field: field_html()
		};
		const column_html = html_map[col.type];

		return `
			<div class="${css_class}">
				${column_html}
			</div>
		`;
	}

	get_meta_html(doc) {
		let html = '';
		if (doc[this.meta.title_field || ''] !== doc.name) {
			html += `
				<div class="level-item hidden-xs hidden-sm ellipsis">
					<a class="text-muted ellipsis" href="${this.get_form_link(doc)}">
						${doc.name}
					</a>
				</div>
			`;
		}
		const modified = comment_when(doc.modified, true);

		const last_assignee = JSON.parse(doc._assign || '[]').slice(-1)[0];
		const assigned_to = last_assignee ?
			`<span class="filterable"
				data-filter="_assign,like,%${last_assignee}%">
				${frappe.avatar(last_assignee)}
			</span>` :
			`<span class="avatar avatar-small avatar-empty"></span>`;

		const comment_count =
			`<span class="${!doc._comment_count ? 'text-extra-muted' : ''} comment-count">
				<i class="octicon octicon-comment-discussion"></i>
				${doc._comment_count > 99 ? "99+" : doc._comment_count}
			</span>`;

		html += `
			<div class="level-item hidden-xs list-row-activity">
				${modified}
				${assigned_to}
				${comment_count}
			</div>
			<div class="level-item visible-xs text-right">
				${this.get_indicator_dot(doc)}
			</div>
		`;

		return html;
	}

	get_count_str() {
		const current_count = this.data.length;

		return frappe.call({
			type: 'GET',
			method: this.method,
			args: {
				doctype: this.doctype,
				filters: this.get_filters_for_args(),
				fields: [`count(distinct ${frappe.model.get_full_column_name('name', this.doctype)}) as total_count`],
			}
		}).then(r => {
			this.total_count = r.message.values[0][0] || current_count;
			const str = __('{0} of {1}', [current_count, this.total_count]);
			return str;
		});
	}

	get_form_link(doc) {
		if (this.settings.get_form_link) {
			return this.settings.get_form_link(doc);
		}

		const docname = doc.name.match(/[%'"]/)
			? encodeURIComponent(doc.name)
			: doc.name;

		return '#Form/' + this.doctype + '/' + docname;
	}

	get_subject_html(doc) {
		let user = frappe.session.user;
		let subject_field = this.columns[0].df;
		let value = doc[subject_field.fieldname] || doc.name;
		let subject = strip_html(value);
		let escaped_subject = frappe.utils.escape_html(subject);

		const liked_by = JSON.parse(doc._liked_by || '[]');
		let heart_class = liked_by.includes(user) ?
			'liked-by' : 'text-extra-muted not-liked';

		const seen = JSON.parse(doc._seen || '[]')
			.includes(user) ? '' : 'bold';

		let subject_html = `
			<input class="level-item list-row-checkbox hidden-xs" type="checkbox" data-name="${doc.name}">
			<span class="level-item" style="margin-bottom: 1px;">
				<i class="octicon octicon-heart like-action ${heart_class}"
					data-name="${doc.name}" data-doctype="${this.doctype}"
					data-liked-by="${encodeURI(doc._liked_by) || '[]'}"
				>
				</i>
				<span class="likes-count">
					${ liked_by.length > 99 ? __("99") + '+' : __(liked_by.length || '')}
				</span>
			</span>
			<span class="level-item ${seen} ellipsis" title="${escaped_subject}">
				<a class="ellipsis" href="${this.get_form_link(doc)}" title="${escaped_subject}">
				${subject}
				</a>
			</span>
		`;

		return subject_html;
	}

	get_indicator_html(doc) {
		const indicator = frappe.get_indicator(doc, this.doctype);
		if (indicator) {
			return `<span class="indicator ${indicator[1]} filterable"
				data-filter='${indicator[2]}'>
				${__(indicator[0])}
			<span>`;
		}
		return '';
	}

	get_indicator_dot(doc) {
		const indicator = frappe.get_indicator(doc, this.doctype);
		if (!indicator) return '';
		return `<span class='indicator ${indicator[1]}' title='${__(indicator[0])}'></span>`;
	}

	setup_events() {
		this.setup_filterable();
		this.setup_list_click();
		this.setup_tag_event();
		this.setup_new_doc_event();
		this.setup_check_events();
		this.setup_like();
		this.setup_realtime_updates();
	}

	setup_filterable() {
		// filterable events
		this.$result.on('click', '.filterable', e => {
			if (e.metaKey || e.ctrlKey) return;
			e.stopPropagation();
			const $this = $(e.currentTarget);
			const filters = $this.attr('data-filter').split('|');

			const filters_to_apply = filters.map(f => {
				f = f.split(',');
				if (f[2] === 'Today') {
					f[2] = frappe.datetime.get_today();
				} else if (f[2] == 'User') {
					f[2] = frappe.session.user;
				}
				return [this.doctype, f[0], f[1], f.slice(2).join(',')];
			});
			this.filter_area.add(filters_to_apply);
		});
	}

	setup_list_click() {
		this.$result.on('click', '.list-row', (e) => {
			const $target = $(e.target);
			// tick checkbox if Ctrl/Meta key is pressed
			if (e.ctrlKey || e.metaKey && !$target.is('a')) {
				const $list_row = $(e.currentTarget);
				const $check = $list_row.find('.list-row-checkbox');
				$check.prop('checked', !$check.prop('checked'));
				e.preventDefault();
				this.on_row_checked();
				return;
			}
			// don't open form when checkbox, like, filterable are clicked
			if ($target.hasClass('filterable') ||
				$target.hasClass('octicon-heart') ||
				$target.is(':checkbox') ||
				$target.is('a')) {
				return;
			}
			// open form
			const $row = $(e.currentTarget);
			const link = $row.find('.list-subject a').get(0);
			if (link) {
				window.location.href = link.href;
				return false;
			}
		});
	}

	setup_check_events() {
		this.$result.on('change', 'input[type=checkbox]', e => {
			const $target = $(e.currentTarget);

			if ($target.is('.list-header-subject .list-check-all')) {
				const $check = this.$result.find('.checkbox-actions .list-check-all');
				$check.prop('checked', $target.prop('checked'));
				$check.trigger('change');
			} else if ($target.is('.checkbox-actions .list-check-all')) {
				const $check = this.$result.find('.list-header-subject .list-check-all');
				$check.prop('checked', $target.prop('checked'));

				this.$result.find('.list-row-checkbox')
					.prop('checked', $target.prop('checked'));
			}

			this.on_row_checked();
		});

		this.$result.on('click', '.list-row-checkbox', e => {
			const $target = $(e.currentTarget);

			// shift select checkboxes
			if (e.shiftKey && this.$checkbox_cursor && !$target.is(this.$checkbox_cursor)) {
				const name_1 = this.$checkbox_cursor.data().name;
				const name_2 = $target.data().name;
				const index_1 = this.data.findIndex(d => d.name === name_1);
				const index_2 = this.data.findIndex(d => d.name === name_2);
				let [min_index, max_index] = [index_1, index_2];

				if (min_index > max_index) {
					[min_index, max_index] = [max_index, min_index];
				}

				let docnames = this.data.slice(min_index + 1, max_index).map(d => d.name);
				const selector = docnames.map(name => `.list-row-checkbox[data-name="${name}"]`).join(',');
				this.$result.find(selector).prop('checked', true);
			}

			this.$checkbox_cursor = $target;
		});
	}

	setup_like() {
		this.$result.on('click', '.like-action', frappe.ui.click_toggle_like);
		this.$result.on('click', '.list-liked-by-me', e => {
			const $this = $(e.currentTarget);
			$this.toggleClass('active');

			if ($this.hasClass('active')) {
				this.filter_area.add(this.doctype, '_liked_by', 'like', '%' + frappe.session.user + '%');
			} else {
				this.filter_area.remove('_liked_by');
			}
		});

		frappe.ui.setup_like_popover(this.$result, '.liked-by');
	}

	setup_new_doc_event() {
		this.$no_result.find('.btn-new-doc').click(() => this.make_new_doc());
	}

	setup_tag_event() {
		this.list_sidebar.parent.on('click', '.list-tag-preview', () => {
			this.toggle_tags();
		});
	}

	setup_realtime_updates() {
		frappe.realtime.on('list_update', data => {
			if (this.filter_area.is_being_edited()) {
				return;
			}

			const { doctype, name } = data;
			if (doctype !== this.doctype) return;

			// filters to get only the doc with this name
			const call_args = this.get_call_args();
			call_args.args.filters.push([this.doctype, 'name', '=', name]);
			call_args.args.start = 0;

			frappe.call(call_args)
				.then(({ message }) => {
					if (!message) return;
					const data = frappe.utils.dict(message.keys, message.values);
					if (!(data && data.length)) {
						// this doc was changed and should not be visible
						// in the listview according to filters applied
						// let's remove it manually
						this.data = this.data.filter(d => d.name !== name);
						this.render();
						return;
					}

					const datum = data[0];
					const index = this.data.findIndex(d => d.name === datum.name);

					if (index === -1) {
						// append new data
						this.data.push(datum);
					} else {
						// update this data in place
						this.data[index] = datum;
					}

					this.data.sort((a, b) => {
						const a_value = a[this.sort_by] || '';
						const b_value = b[this.sort_by] || '';

						let return_value = 0;
						if (a_value > b_value) {
							return_value = 1;
						}

						if (b_value > a_value) {
							return_value = -1;
						}

						if (this.sort_order === 'desc') {
							return_value = -return_value;
						}
						return return_value;
					});

					this.render();
				});
		});
	}

	on_row_checked() {
		this.$list_head_subject = this.$list_head_subject || this.$result.find('header .list-header-subject');
		this.$checkbox_actions = this.$checkbox_actions || this.$result.find('header .checkbox-actions');

		this.$checks = this.$result.find('.list-row-checkbox:checked');

		this.$list_head_subject.toggle(this.$checks.length === 0);
		this.$checkbox_actions.toggle(this.$checks.length > 0);

		if (this.$checks.length === 0) {
			this.$list_head_subject.find('.list-check-all').prop('checked', false);
		} else {
			this.$checkbox_actions.find('.list-header-meta').html(
				__('{0} items selected', [this.$checks.length])
			);
			this.$checkbox_actions.show();
			this.$list_head_subject.hide();
		}
		this.toggle_actions_menu_button(this.$checks.length > 0);
	}

	toggle_tags() {
		this.$result.toggleClass('tags-shown');
	}

	get_checked_items(only_docnames) {
		const docnames = Array.from(this.$checks || [])
			.map(check => $(check).data().name);

		if (only_docnames) return docnames;

		return this.data.filter(d => docnames.includes(d.name));
	}

	save_view_user_settings(obj) {
		return frappe.model.user_settings.save(this.doctype, this.view_name, obj);
	}

	on_update() {

	}

	get_share_url() {
		const query_params = this.get_filters_for_args().map(filter => {
			filter[3] = encodeURIComponent(filter[3]);
			if (filter[2] === '=') {
				return `${filter[1]}=${filter[3]}`;
			}
			return [filter[1], '=', JSON.stringify([filter[2], filter[3]])].join('');
		}).join('&');

		let full_url = window.location.href;
		if (query_params) {
			full_url += '?' + query_params;
		}
		return full_url;
	}

	share_url() {
		const d = new frappe.ui.Dialog({
			title: __('Share URL'),
			fields: [
				{
					fieldtype: 'Code',
					fieldname: 'url',
					label: 'URL',
					default: this.get_share_url(),
					read_only: 1
				}
			]
		});
		d.show();
	}

	get_menu_items() {
		const doctype = this.doctype;
		const items = [];

		if (frappe.model.can_import(doctype)) {
			items.push({
				label: __('Import'),
				action: () => frappe.set_route('List', 'Data Import', {
					reference_doctype: doctype
				}),
				standard: true
			});
		}

		if (frappe.model.can_set_user_permissions(doctype)) {
			items.push({
				label: __('User Permissions'),
				action: () => frappe.set_route('List', 'User Permission', {
					allow: doctype
				}),
				standard: true
			});
		}

		if (frappe.user_roles.includes('System Manager')) {
			items.push({
				label: __('Role Permissions Manager'),
				action: () => frappe.set_route('permission-manager', {
					doctype
				}),
				standard: true
			});

			items.push({
				label: __('Customize'),
				action: () => frappe.set_route('Form', 'Customize Form', {
					doc_type: doctype
				}),
				standard: true
			});
		}

		items.push({
			label: __('Toggle Sidebar'),
			action: () => this.toggle_side_bar(),
			standard: true
		});

		items.push({
			label: __('Share URL'),
			action: () => this.share_url(),
			standard: true
		});

		// add to desktop
		items.push({
			label: __('Add to Desktop'),
			action: () => frappe.add_to_desktop(doctype, doctype),
			standard: true
		});

		if (frappe.user.has_role('System Manager') && frappe.boot.developer_mode === 1) {
			// edit doctype
			items.push({
				label: __('Edit DocType'),
				action: () => frappe.set_route('Form', 'DocType', doctype),
				standard: true
			});
		}

		return items;
	}

	get_actions_menu_items() {
		const doctype = this.doctype;
		const actions_menu_items = [];
		const bulk_operations = new BulkOperations({ doctype: this.doctype });

		const is_field_editable = (field_doc) => {
			return field_doc.fieldname && frappe.model.is_value_type(field_doc)
				&& field_doc.fieldtype !== 'Read Only' && !field_doc.hidden && !field_doc.read_only;
		};

		const has_editable_fields = (doctype) => {
			return frappe.meta.get_docfields(doctype).some(field_doc => is_field_editable(field_doc));
		};

		const has_submit_permission = (doctype) => {
			return frappe.perm.has_perm(doctype, 0, 'submit');
		};

		// utility
		const bulk_assignment = () => {
			return {
				label: __('Assign To'),
				action: () => bulk_operations.assign(this.get_checked_items(true), this.refresh),
				standard: true
			};
		};

		const bulk_printing = () => {
			return {
				label: __('Print'),
				action: () => bulk_operations.print(this.get_checked_items()),
				standard: true
			};
		};

		const bulk_delete = () => {
			return {
				label: __('Delete'),
				action: () => {
					const docnames = this.get_checked_items(true);
					frappe.confirm(__('Delete {0} items permanently?', [docnames.length]),
						() => bulk_operations.delete(docnames, this.refresh));
				},
				standard: true,
			};
		};

		const bulk_cancel = () => {
			return {
				label: __('Cancel'),
				action: () => {
					const docnames = this.get_checked_items(true);
					if (docnames.length > 0) {
						frappe.confirm(__('Cancel {0} documents?', [docnames.length]),
							() => bulk_operations.submit_or_cancel(docnames, 'cancel', this.refresh));
					}
				},
				standard: true
			};
		};

		const bulk_submit = () => {
			return {
				label: __('Submit'),
				action: () => {
					const docnames = this.get_checked_items(true);
					if (docnames.length > 0) {
						frappe.confirm(__('Submit {0} documents?', [docnames.length]),
							() => bulk_operations.submit_or_cancel(docnames, 'submit', this.refresh));
					}
				},
				standard: true
			};
		};

		const bulk_edit = () => {
			return {
				label: __('Edit'),
				action: () => {
					let field_mappings = {};

					frappe.meta.get_docfields(doctype).forEach(field_doc => {
						if (is_field_editable(field_doc)) {
							field_mappings[field_doc.label] = Object.assign({}, field_doc);
						}
					});

					const docnames = this.get_checked_items(true);

					bulk_operations.edit(docnames, field_mappings, this.refresh);
				},
				standard: true
			};
		};

		// bulk edit
		if (has_editable_fields(doctype)) {
			actions_menu_items.push(bulk_edit());
		}

		// bulk assignment
		actions_menu_items.push(bulk_assignment());

		// bulk printing
		if (frappe.model.can_print(doctype)) {
			actions_menu_items.push(bulk_printing());
		}

		// Bulk submit
		if (frappe.model.is_submittable(doctype) && has_submit_permission(doctype)) {
			actions_menu_items.push(bulk_submit());
		}

		// Bulk cancel
		if (frappe.model.can_cancel(doctype)) {
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

			if (typeof value === 'string' && value.startsWith('[') && value.endsWith(']')) {
				value = JSON.parse(value);
			}

			// if `Child DocType.fieldname`
			if (field.includes('.')) {
				doctype = field.split('.')[0];
				field = field.split('.')[1];
			}

			// find the table in which the key exists
			// for example the filter could be {"item_code": "X"}
			// where item_code is in the child table.

			// we can search all tables for mapping the doctype
			if (!doctype) {
				doctype = frappe.meta.get_doctype_for_field(this.doctype, field);
			}

			if (doctype) {
				if ($.isArray(value)) {
					filters.push([doctype, field, value[0], value[1]]);
				} else {
					filters.push([doctype, field, "=", value]);
				}
			}
		}

		return filters;
	}

	static trigger_list_update(data) {
		const doctype = data.doctype;
		if (!doctype) return;
		frappe.provide('frappe.views.trees');

		// refresh tree view
		if (frappe.views.trees[doctype]) {
			frappe.views.trees[doctype].tree.refresh();
			return;
		}

		// refresh list view
		const page_name = frappe.get_route_str();
		const list_view = frappe.views.list_view[page_name];
		list_view && list_view.on_update(data);
	}
};

$(document).on('save', (event, doc) => {
	frappe.views.ListView.trigger_list_update(doc);
});
