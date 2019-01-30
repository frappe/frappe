frappe.provide('frappe.views');

frappe.views.FileView = class FileView extends frappe.views.ListView {
	static load_last_view() {
		const route = frappe.get_route();
		if (route.length === 2) {
			const view_user_settings = frappe.get_user_settings('File', 'File');
			frappe.set_route('List', 'File', view_user_settings.last_folder || frappe.boot.home_folder);
			return true;
		}
		return redirect_to_home_if_invalid_route();
	}

	get view_name() {
		return 'File';
	}

	show() {
		if (!redirect_to_home_if_invalid_route()) {
			super.show();
		}
	}

	setup_view() {
		this.render_header();
		this.setup_events();
	}

	set_breadcrumbs() {
		const route = frappe.get_route();
		route.splice(-1);
		const last_folder = route[route.length - 1];
		if (last_folder === 'File') return;

		frappe.breadcrumbs.add({
			type: 'Custom',
			label: __('Home'),
			route: '#List/File/Home'
		});
	}

	setup_defaults() {
		super.setup_defaults();
		this.page_title = __('File Manager');

		const route = frappe.get_route();
		this.current_folder = route.slice(2).join('/');
		this.filters = [['File', 'folder', '=', this.current_folder, true]];
		this.order_by = this.view_user_settings.order_by || 'file_name asc';

		this.menu_items = this.menu_items.concat(this.file_menu_items());
	}

	file_menu_items() {
		const items = [
			{
				label: __('Home'),
				action: () => {
					frappe.set_route('List', 'File', 'Home');
				},
			},
			{
				label: __('Cut'),
				action: () => {
					frappe.file_manager.cut(this.get_checked_items(), this.current_folder);
				},
				class: 'cut-menu-button hide'
			},
			{
				label: __('Paste'),
				action: () => {
					frappe.file_manager.paste(this.current_folder);
				},
				class: 'paste-menu-button hide'
			},
			{
				label: __('New Folder'),
				action: () => {
					frappe.prompt(__('Name'), (values) => {
						if((values.value.indexOf("/") > -1)) {
							frappe.throw(__("Folder name should not include '/' (slash)"));
						}
						const data =  {
							file_name: values.value,
							folder: this.current_folder
						};
						frappe.call({
							method: "frappe.core.doctype.file.file.create_new_folder",
							args: data
						});
					}, __('Enter folder name'), __('Create'));
				}
			},
			{
				label: __('Toggle Grid View'),
				action: () => {
					frappe.views.FileView.grid_view = !frappe.views.FileView.grid_view;
					this.refresh();
				}
			},
			{
				label: __('Import Zip'),
				action: () => {
					// make upload dialog
					frappe.ui.get_upload_dialog({
						args: {
							folder: this.current_folder,
							from_form: 1
						},
						callback: (attachment, r) => {
							frappe.call({
								method: 'frappe.core.doctype.file.file.unzip_file',
								args: {
									name: r.message.name,
								},
								callback: function (r) {
									if(r.exc) {
										frappe.msgprint(__('Error in uploading files' + r.exc));
									}
								}
							});
						},
					});
				}
			}
		];

		return items;
	}

	set_fields() {
		this.fields = this.meta.fields
			.filter(df => frappe.model.is_value_type(df.fieldtype) && !df.hidden)
			.map(df => df.fieldname)
			.concat(['name', 'modified', 'creation']);
	}

	prepare_data(data) {
		super.prepare_data(data);

		this.data = this.data.map(d => this.prepare_datum(d));

		// Bring folders to the top
		const { sort_by } = this.sort_selector;
		if (sort_by === 'file_name') {
			this.data.sort((a, b) => {
				if (a.is_folder && !b.is_folder) {
					return -1;
				}
				if (!a.is_folder &&b.is_folder) {
					return 1;
				}
				return 0;
			});
		}
	}

	prepare_datum(d) {
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
		d._title = title;
		d.icon_class = icon_class;

		d.subject_html = `
			<i class="${icon_class} text-muted" style="width: 16px;"></i>
			<span>${title}</span>
			${d.is_private ? '<i class="fa fa-lock fa-fw text-warning"></i>' : ''}
		`;
		return d;
	}

	before_render() {
		super.before_render();
		frappe.model.user_settings.save('File', 'grid_view', frappe.views.FileView.grid_view);
		this.save_view_user_settings({
			last_folder: this.current_folder,
		});
	}

	render() {
		this.$result.removeClass('file-grid');
		if (frappe.views.FileView.grid_view) {
			this.render_grid_view();
		} else {
			super.render();
		}
	}

	render_grid_view() {
		let html = '';

		html = this.data.map(d => {
			return `
				<a href="${this.get_route_url(d)}">
					<div class="file-wrapper padding flex small">
						<div class="file-icon text-muted">
							<span class="${d.icon_class} mega-octicon"></span>
						</div>
						<div class="file-title ellipsis">${d._title}</div>
					</div>
				</a>
			`;
		}).join('');
		this.$result.addClass('file-grid');
		this.$result.html(html);
	}

	get_breadcrumbs_html() {
		const route = frappe.get_route();
		const folders = route.slice(2);

		return folders
			.map((folder, i) => {
				if (i === folders.length - 1) {
					return `<span>${folder}</span>`;
				}
				const route = folders.reduce((acc, curr, j) => {
					if (j <= i) {
						acc += '/' + curr;
					}
					return acc;
				}, '#List/File');

				return `<a href="${route}">${folder}</a>`;
			})
			// only show last 3 breadcrumbs
			.slice(-3)
			.join('&nbsp;/&nbsp;');
	}

	get_header_html() {
		const breadcrumbs_html = this.get_breadcrumbs_html();

		let subject_html = `
			<div class="list-row-col list-subject level">
				<input class="level-item list-check-all hidden-xs" type="checkbox" title="${__("Select All")}">
				<span class="level-item">${breadcrumbs_html}</span>
			</div>
			<div class="list-row-col ellipsis hidden-xs">
				<span>${__('Size')}</span>
			</div>
			<div class="list-row-col ellipsis hidden-xs">
				<span>${__('Created')}</span>
			</div>
		`;

		return this.get_header_html_skeleton(subject_html, '<span class="list-count"></span>');
	}

	get_route_url(file) {
		return file.is_folder ? '#List/File/' + file.name : this.get_form_link(file);
	}

	get_left_html(file) {
		file = this.prepare_datum(file);
		const file_size = frappe.form.formatters.FileSize(file.file_size);
		const route_url = this.get_route_url(file);

		let created_on;
		const [date] = file.creation.split(' ');
		if (date === frappe.datetime.now_date()) {
			created_on = comment_when(file.creation);
		} else {
			created_on = frappe.datetime.str_to_user(date);
		}

		return `
			<div class="list-row-col ellipsis list-subject level">
				<input class="level-item list-row-checkbox hidden-xs" type="checkbox" data-name="${file.name}">
				<span class="level-item  ellipsis" title="${file.file_name}">
					<a class="ellipsis" href="${route_url}" title="${file.file_name}">
						${file.subject_html}
					</a>
				</span>
			</div>
			<div class="list-row-col ellipsis hidden-xs text-muted">
				<span>${file_size}</span>
			</div>
			<div class="list-row-col ellipsis hidden-xs text-muted">
				<span>${created_on}</span>
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

	setup_events() {
		super.setup_events();
		this.setup_drag_drop();
	}

	setup_drag_drop() {
		this.$result.on('dragenter dragover', false)
			.on('drop', e => {
				var dataTransfer = e.originalEvent.dataTransfer;
				if (!(dataTransfer && dataTransfer.files && dataTransfer.files.length > 0)) {
					return;
				}
				e.stopPropagation();
				e.preventDefault();
				frappe.upload.make({
					files: dataTransfer.files,
					"args": {
						"folder": this.current_folder,
						"from_form": 1
					}
				});
			});
	}

	toggle_result_area() {
		super.toggle_result_area();
		this.toggle_cut_paste_buttons();
	}

	on_row_checked() {
		super.on_row_checked();
		this.toggle_cut_paste_buttons();
	}

	toggle_cut_paste_buttons() {
		// paste btn
		const $paste_btn = this.page.menu_btn_group.find('.paste-menu-button');
		const hide = !frappe.file_manager.can_paste ||
			frappe.file_manager.old_folder === this.current_folder;

		if (hide) {
			$paste_btn.addClass('hide');
		} else {
			$paste_btn.removeClass('hide');
		}

		// cut btn
		const $cut_btn = this.page.menu_btn_group.find('.cut-menu-button');
		if (this.$checks && this.$checks.length > 0) {
			$cut_btn.removeClass('hide');
		} else {
			$cut_btn.addClass('hide');
		}
	}
};

frappe.views.FileView.grid_view = frappe.get_user_settings('File').grid_view || false;

function redirect_to_home_if_invalid_route() {
	const route = frappe.get_route();
	if (route[2] !== 'Home') {
		// if the user somehow redirects to List/File/List
		// redirect back to Home
		frappe.set_route('List', 'File', 'Home');
		return true;
	}
	return false;
}
