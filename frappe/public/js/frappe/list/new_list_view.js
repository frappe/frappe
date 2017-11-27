frappe.provide('frappe.views');

frappe.views.ListView = class ListView extends frappe.views.BaseList {
	constructor(opts) {
		super(opts);
		this.parent.list_view = this;

		if (this.load_last_view()) {
			return;
		}
		// route has a view
		this.view = this.route[2];
		if (this.view !== this.view_name) {
			return new frappe.views[this.view + 'View']({
				doctype: this.doctype,
				parent: this.parent
			});
		}

		// required to set cur_list
		this.parent.list_view = this;
		this.show();
	}

	get view_name() {
		return 'List';
	}

	show() {
		if (this.load_last_view()) {
			return;
		}
		super.show();
	}

	load_last_view() {
		const re_route = this.build_route();
		if (re_route) {
			frappe.set_route(this.route);
			return true;
		}
		return false;
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

	setup_view() {
		this.setup_columns();
		this.setup_filterable();
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

		const fields_in_list_view = this.fields_in_list_view;
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

	toggle_result_area() {
		this.$result.toggle(this.data.length > 0);
		this.$paging_area.toggle(this.data.length > 0);
		this.$no_result.toggle(this.data.length == 0);
		this.$paging_area.find('.btn-more')
			.toggle(this.data.length >= this.page_length);
	}

	render() {
		this.toggle_result_area();

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
			<input class="level-item list-select-all hidden-xs" type="checkbox" title="${__("Select All")}" style="margin-top: 0">
			<span class="level-item list-liked-by" style="margin-bottom: 1px;">
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
				<div class="level-left">
					${$columns}
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
				<div class="level-right text-muted">
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
		let subject = doc[subject_field.fieldname];

		const liked_by = JSON.parse(doc._liked_by || '[]');
		let heart_class = liked_by.includes(user) ?
			'liked-by-user' : 'text-extra-muted';

		const seen = JSON.parse(doc._seen || '[]')
			.includes(user) ? 'seen' : '';

		let subject_html = `
			<input class="level-item list-row-checkbox hidden-xs"
				type="checkbox" style="margin-top: 0"
				data-name="${doc.name}"
			>
			<span class="level-item list-row-like"
				style="margin-bottom: 1px;"
				data-liked-by="${doc._liked_by || "[]"}"
			>
				<i class="octicon octicon-heart ${heart_class}"
					data-name="{{ _name }}" data-doctype="{{ doctype }}"
				>
				</i>
				<span class="likes-count">
					${ liked_by.length > 99 ? __("99") + '+' : __(liked_by.length || '')}
				</span>
			</span>
			<span class="level-item ${seen} ellipsis" title="${subject}">
				<a class="ellipsis" href="${this.get_form_link(doc)}" title="${subject}">
				${strip_html(subject)}
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

	setup_filterable() {
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

			filters_to_apply.map(f => {
				this.filter_area.add(...f);
			});

			if (filters_to_apply.length > 0) {
				this.refresh(true);
			}
		});

		this.$result.on('click', '.list-row', function (e) {
			// don't open in case of checkbox, like, filterable
			if ($(e.target).hasClass('filterable')
				|| $(e.target).hasClass('octicon-heart')
				|| $(e.target).is(':checkbox')
				|| $(e.target).is('a')
			) {
				return;
			}

			const link = $(this).find('.list-subject a').get(0);
			window.location.href = link.href;
			return false;
		});
	}
}