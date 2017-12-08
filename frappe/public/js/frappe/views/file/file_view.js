frappe.provide('frappe.views');

frappe.views.FileView = class FileView extends frappe.views.ListView {
	static load_last_view() {
		const route = frappe.get_route();
		if (route.length === 2) {
			const view_user_settings = frappe.get_user_settings('File', 'File')
			frappe.set_route('List', 'File', view_user_settings.last_folder || frappe.boot.home_folder);
			return true;
		}
		return false;
	}

	setup_view() {
		this.setup_events();
	}

	set_breadcrumbs() {
		const route = frappe.get_route();
		route.splice(-1);
		const last_folder = route[route.length - 1];
		if (last_folder === 'File') return;

		const last_folder_route = '#' + route.join('/');
		frappe.breadcrumbs.add({
			type: 'Custom',
			label: last_folder,
			route: last_folder_route
		});
	}

	setup_defaults() {
		super.setup_defaults();
		this.page_title = __('File Manager');

		const route = frappe.get_route();
		this.current_folder = route.slice(2).join('/');
		this.filters = [['File', 'folder', '=', this.current_folder, true]];
		this.order_by = this.view_user_settings.order_by || 'file_name asc';
	}

	set_fields() {
		this._fields = this.meta.fields
			.filter(df => frappe.model.is_value_type(df.fieldtype) && !df.hidden)
			.map(df => df.fieldname)
			.concat(['name', 'modified']);
	}

	update_data(data) {
		super.update_data(data);

		this.data = this.data.map(d => {
			let icon_class = '';
			if (d.is_folder) {
				icon_class = "octicon octicon-file-directory";
			} else if (frappe.utils.is_image_file(d.file_name)) {
				icon_class = "octicon octicon-file-media";
			} else {
				icon_class = 'octicon octicon-file-text';
			}

			let title = d.file_name || d.file_url;
			title = title.slice(0, 60);

			d._title = `
				<i class="${icon_class} text-muted" style="width: 16px;"></i>
				<span>${title}</span>
				${d.is_private ? '<i class="fa fa-lock fa-fw text-warning"></i>' : ''}
			`;
			return d;
		});
	}

	before_render() {
		super.before_render();
		this.save_view_user_settings({
			last_folder: this.current_folder
		});
	}

	get_header_html() {
		let subject_html = `
			<div class="list-row-col list-subject level">
				<input class="level-item list-check-all hidden-xs" type="checkbox" title="${__("Select All")}">
				<span class="level-item">${__('File Name')}</span>
			</div>
			<div class="list-row-col ellipsis hidden-xs text-right">
				<span>${__('File Size')}</span>
			</div>
		`;

		return this.get_header_html_skeleton(subject_html, '<span class="list-count"></span>')
	}

	get_left_html(file) {
		const file_size = frappe.form.formatters.FileSize(file.file_size)
		const route_url = file.is_folder ? '#List/File/' + file.name : this.get_form_link(file);

		return `
			<div class="list-row-col ellipsis list-subject level">
				<input class="level-item list-row-checkbox hidden-xs" type="checkbox" data-name="${file.name}">
				<span class="level-item  ellipsis" title="${file.file_name}">
					<a class="ellipsis" href="${route_url}" title="${file.file_name}">
						${file._title}
					</a>
				</span>
			</div>
			<div class="list-row-col ellipsis hidden-xs text-muted text-right">
				<span>${file_size}</span>
			</div>
		`;
	}

	get_right_html(file) {
		return `
			<div class="level-item list-row-activity">
				${comment_when(file.modified)}
			</div>
		`;
	}

	make_new_doc() {
		frappe.ui.get_upload_dialog({
			"args": {
				"folder": this.current_folder,
				"from_form": 1
			},
			callback:() => this.refresh()
		});
	}
};