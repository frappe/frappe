frappe.provide('frappe.views');

frappe.views.ListView = class ListView extends frappe.views.BaseList {

	get view_name() {
		// ListView -> List
		return this.constructor.name.split('View')[0];
	}

	show() {
		super.show();
		frappe.model.user_settings.save(this.doctype, 'last_view', this.view_name);
	}

	init() {
		super.init();
		// throttle refresh for 1s
		this.refresh = frappe.utils.throttle(this.refresh, 1000);

		this.load_lib = new Promise(resolve => {
			if (this.required_libs) {
				frappe.require(this.required_libs, resolve);
			} else {
				resolve();
			}
		});
	}

	setup_defaults() {
		super.setup_defaults();
		this.view_user_settings = this.user_settings[this.view_name] || {};
	}

	set_fields() {
		// get from user_settings
		if (this.view_user_settings.fields) {
			this._fields = this.view_user_settings.fields;
			return;
		}
		// build from meta
		super.set_fields();
	}

	build_fields() {
		super.build_fields();
		// save in user_settings
		this.save_view_user_settings({
			fields: this._fields
		});
	}

	setup_page_head() {
		super.setup_page_head();
		this.set_primary_action();
	}

	set_primary_action() {
		if (this.can_create) {
			this.page.set_primary_action(__('New'), () => {
				this.make_new_doc();
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
		frappe.new_doc(doctype);
	}

	setup_filter_area() {
		super.setup_filter_area();
		// initialize with saved filters
		const saved_filters = this.view_user_settings.filters;
		if (saved_filters && saved_filters.length > 0) {
			this._setup = this.filter_area.add(saved_filters);
		}
	}

	setup_view() {
		this.setup_columns();
		this.setup_events();
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
			fields_in_list_view.map(df => ({
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

	freeze(toggle) {
		if (this.view_name !== 'List') return;

		this.$freeze.toggle(toggle);
		this.$result.toggle(!toggle);

		const columns = this.columns;
		if (toggle) {
			if (this.$freeze.find('.freeze-row').length > 0) return;

			const html = `
				${this.get_header_html()}
				${Array.from(new Array(10)).map(loading_row).join('')}
			`;
			this.$freeze.html(html);
		}

		function loading_row() {
			return `
				<div class="list-row freeze-row level">
					<div class="level-left">
						<div class="list-row-col list-subject"></div>
						${columns.slice(1).map(c =>
							`<div class="list-row-col"></div>`
						).join('')}
					</div>
					<div class="level-right"></div>
				</div>
			`;
		}
	}

	before_render() {
		this.save_view_user_settings({
			filters: this.filter_area.get()
		});
	}

	render() {

		if (!this.start === 0) {
			// append new rows
		}

		if (this.data.length > 0) {
			const html = `
				${this.get_header_html()}
				${this.data.map(doc => this.get_list_row_html(doc)).join('')}
			`;
			this.$result.html(html);
		}
		this.get_count_html()
			.then(html => {
				this.$result.find('.list-count').html(html);
			});
	}

	get_header_html() {
		const subject_field = this.columns[0].df;
		let subject_html = `
			<input class="level-item list-check-all hidden-xs" type="checkbox" title="${__("Select All")}" style="margin-top: 0">
			<span class="level-item list-liked-by-me" style="margin-bottom: 1px;">
				<i class="octicon octicon-heart text-extra-muted" title="${__("Likes")}"></i>
			</span>
			<span class="level-item">${__(subject_field.label)}</span>
		`;
		const $columns = this.columns.map(col => {
			let classes = [
				'list-row-col',
				col.type == 'Subject' ? 'list-subject level' : 'hidden-xs',
				frappe.model.is_numeric_field(col.df) ? 'text-right' : ''
			].join(' ');

			return `
				<div class="${classes}">
					${col.type === 'Subject' ?
					subject_html :
					`<span>${__(col.df && col.df.label || col.type)}</span>`
				}
				</div>
			`;
		}).join('');

		return `
			<header class="level list-row list-row-head text-muted small">
				<div class="level-left list-header-subject">
					${$columns}
				</div>
				<div class="level-left checkbox-actions">
					<div class="level list-subject">
						<input class="level-item list-check-all hidden-xs" type="checkbox" title="${__("Select All")}" style="margin-top: 0">
						<span class="level-item list-header-meta"></span>
					</div>
				</div>
				<div class="level-right">
					<span class="list-count"></span>
				</div>
			</header>
		`;
	}

	get_list_row_html(doc) {
		const $columns = this.columns.map(col => this.get_column_html(col, doc)).join('');
		const $meta = this.get_meta_html(doc);

		return `
			<div class="level list-row small">
				<div class="level-left">
					${$columns}
				</div>
				<div class="level-right text-muted ellipsis">
					${$meta}
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
		const value = doc[fieldname];

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
		}

		const field_html = () => {
			let html;
			if (df.fieldtype === 'Image') {
				html = df.options ?
					`<img src="${doc[df.options]}" style="max-height: 30px; max-width: 100%;">` :
					`<div class="missing-image small">
						<span class="octicon octicon-circle-slash"></span>
					</div>`;
			} else if (df.fieldtype === 'Select') {
				html = `<span class="filterable indicator ${frappe.utils.guess_colour(value)} ellipsis"
					data-filter="${fieldname},=,${value}">
					${__(value)}
				</span>`;
			} else if (df.fieldtype === 'Link') {
				html = `<a class="filterable text-muted ellipsis"
					data-filter="${fieldname},=,${value}">
					${value}
				</a>`;
			} else {
				html = `<a class="filterable text-muted ellipsis"
					data-filter="${fieldname},=,${value}">
					${format()}
				</a>`;
			}

			return `<span class="ellipsis"
				title="${label + ': ' + value}">
				${html}
			</span>`;
		}

		const class_map = {
			Subject: 'list-subject level',
			Field: 'hidden-xs'
		}
		const css_class = [
			'list-row-col ellipsis',
			class_map[col.type],
			frappe.model.is_numeric_field(df) ? 'text-right' : ''
		].join(' ');

		const html_map = {
			Subject: this.get_subject_html(doc),
			Field: field_html()
		}
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
			`<span class="${!doc._comment_count ? 'text-extra-muted' : ''}">
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

	get_count_html() {
		const current_count = this.data.length;

		return frappe.call({
			method: 'frappe.model.db_query.get_count',
			args: {
				doctype: this.doctype,
				filters: this.filter_area.get()
			}
		}).then(r => {
			const count = r.message || current_count;
			const str = __('{0} of {1}', [current_count, count]);
			const html = `<span>${str}</span>`;
			return html;
		});
	}

	get_form_link(doc) {
		return '#Form/' + this.doctype + '/' + doc.name;
	}

	get_subject_html(doc) {
		let user = frappe.session.user;
		let subject_field = this.columns[0].df;
		let subject = strip_html(doc[subject_field.fieldname]);

		const liked_by = JSON.parse(doc._liked_by || '[]');
		let heart_class = liked_by.includes(user) ?
			'liked-by' : 'text-extra-muted not-liked';

		const seen = JSON.parse(doc._seen || '[]')
			.includes(user) ? 'seen' : '';

		let subject_html = `
			<input class="level-item list-row-checkbox hidden-xs"
				type="checkbox" style="margin-top: 0"
				data-name="${doc.name}"
			>
			<span class="level-item"
				style="margin-bottom: 1px;"
			>
				<i class="octicon octicon-heart like-action ${heart_class}"
					data-name="${doc.name}" data-doctype="${this.doctype}"
					data-liked-by="${encodeURI(doc._liked_by) || '[]'}"
				>
				</i>
				<span class="likes-count">
					${ liked_by.length > 99 ? __("99") + '+' : __(liked_by.length || '')}
				</span>
			</span>
			<span class="level-item ${seen} ellipsis" title="${subject}">
				<a class="ellipsis" href="${this.get_form_link(doc)}" title="${subject}">
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
		// filterable events
		this.$result.on('click', '.filterable', e => {
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
				return [this.doctype, f[0], f[1], f.slice(2).join(',')]
			});
			this.filter_area.add(filters_to_apply);
		});

		this.$result.on('click', '.list-row', (e) => {
			const $target = $(e.target);

			// don't open form when checkbox, like, filterable are clicked
			if ($target.hasClass('filterable')
				|| $target.hasClass('octicon-heart')
				|| $target.is(':checkbox')
				|| $target.is('a')
			) {
				return;
			}

			// open form
			const link = $(this).find('.list-subject a').get(0);
			if (link) {
				window.location.href = link.href;
				return false;
			}
		});

		this.$no_result.find('.btn-new-doc').click(() => this.make_new_doc());

		this.setup_check_events();
		this.setup_like();
	}

	setup_check_events() {
		this.$result.on('change', 'input[type=checkbox]', e => {
			const $target = $(e.currentTarget);

			if ($target.is('.list-header-subject .list-check-all')) {
				const $check = this.$result.find('.checkbox-actions .list-check-all');
				$check.prop('checked', $target.prop('checked'));
				$check.trigger('change');
			}
			else if ($target.is('.checkbox-actions .list-check-all')) {
				const $check = this.$result.find('.list-header-subject .list-check-all');
				$check.prop('checked', $target.prop('checked'));

				this.$result.find('.list-row-checkbox')
					.prop('checked', $target.prop('checked'));
			}

			this.on_row_checked();
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

	on_row_checked() {
		this.$list_head_subject = this.$list_head_subject || this.$result.find('header .list-header-subject');
		this.$checkbox_actions = this.$checkbox_actions || this.$result.find('header .checkbox-actions');

		const $checks = this.$result.find('.list-row-checkbox:checked');


		this.$list_head_subject.toggle($checks.length === 0);
		this.$checkbox_actions.toggle($checks.length > 0);

		if ($checks.length === 0) {
			this.$list_head_subject.find('.list-select-all').prop('checked', false);
		} else {
			this.$checkbox_actions.find('.list-header-meta').html(
				__('{0} items selected', [$checks.length])
			);
			this.$checkbox_actions.show();
			this.$list_head_subject.hide();
		}

		if (this.can_delete) {
			this.toggle_delete_button($checks.length > 0);
		}
	}

	toggle_delete_button(toggle) {
		if (toggle) {
			this.page.set_primary_action(__('Delete'),
				() => this.delete_items(),
				'octicon octicon-trashcan'
			).addClass('btn-danger');
		} else {
			this.page.btn_primary.removeClass('btn-danger');
			this.set_primary_action();
		}
	}

	delete_items() {
		const docnames = this.get_checked_items();

		frappe.confirm(__('Delete {0} items permanently?', [docnames.length]),
			() => {
				frappe.call({
					method: 'frappe.desk.reportview.delete_items',
					freeze: true,
					args: {
						items: docnames,
						doctype: this.doctype
					}
				})
					.then(() => {
						frappe.utils.play_sound('delete');
						this.refresh(true);
					});
			}
		);
	}

	get_checked_items(only_docnames) {
		const docnames = Array.from(this.$result.find('.list-row-checkbox:checked'))
			.map(check => $(check).data().name);

		if (only_docnames) return docnames;

		return this.data.filter(d => docnames.includes(d.name));
	}

	save_view_user_settings(obj) {
		return frappe.model.user_settings.save(this.doctype, this.view_name, obj);
	}

	on_update(data) {
		if (data.doctype === this.doctype) {
			this.refresh();
		}
	}

	static trigger_list_update(data) {
		const doctype = data.doctype;
		if (!doctype) return;

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
}

$(document).on('save', function (event, doc) {
	frappe.views.ListView.trigger_list_update(doc);
});
