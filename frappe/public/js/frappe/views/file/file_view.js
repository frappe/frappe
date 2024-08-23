frappe.provide("frappe.views");

frappe.views.FileView = class FileView extends frappe.views.ListView {
	static load_last_view() {
		const route = frappe.get_route();
		if (route.length === 2) {
			const view_user_settings = frappe.get_user_settings("File", "File");
			frappe.set_route(
				"List",
				"File",
				view_user_settings.last_folder || frappe.boot.home_folder
			);
			return true;
		}
		return redirect_to_home_if_invalid_route();
	}

	get view_name() {
		return "File";
	}

	show() {
		if (!redirect_to_home_if_invalid_route()) {
			super.show();
		}
	}

	setup_view() {
		this.render_header();
		this.setup_events();
		this.$page.find(".layout-main-section-wrapper").addClass("file-view");
		this.add_file_action_buttons();
		this.page.add_button(__("Toggle Grid View"), () => {
			frappe.views.FileView.grid_view = !frappe.views.FileView.grid_view;
			this.refresh();
		});
	}

	setup_no_result_area() {
		this.$no_result = $(`<div class="no-result">
			<div class="breadcrumbs">${this.get_breadcrumbs_html()}</div>
			<div class="text-muted flex justify-center align-center">
				${this.get_no_result_message()}
			</div>
		</div>`).hide();
		this.$frappe_list.append(this.$no_result);
	}

	get_args() {
		let args = super.get_args();
		if (frappe.views.FileView.grid_view) {
			Object.assign(args, {
				order_by: `is_folder desc, ${this.sort_by} ${this.sort_order}`,
			});
		}
		return args;
	}

	set_breadcrumbs() {
		const route = frappe.get_route();
		route.splice(-1);
		const last_folder = route[route.length - 1];
		if (last_folder === "File") return;

		frappe.breadcrumbs.add({
			type: "Custom",
			label: __("Home"),
			route: "/app/List/File/Home",
		});
	}

	setup_defaults() {
		return super.setup_defaults().then(() => {
			this.page_title = __("File Manager");

			const route = frappe.get_route();
			this.current_folder = route.slice(2).join("/") || "Home";
			this.filters = [["File", "folder", "=", this.current_folder, true]];
			this.order_by = this.view_user_settings.order_by || "file_name asc";

			this.menu_items = this.menu_items.concat(this.file_menu_items());
		});
	}

	file_menu_items() {
		return [
			{
				label: __("Home"),
				action: () => {
					frappe.set_route("List", "File", "Home");
				},
			},
			{
				label: __("New Folder"),
				action: () => {
					frappe.prompt(
						__("Name"),
						(values) => {
							if (values.value.indexOf("/") > -1) {
								frappe.throw(__("Folder name should not include '/' (slash)"));
							}
							const data = {
								file_name: values.value,
								folder: this.current_folder,
							};
							frappe.call({
								method: "frappe.core.api.file.create_new_folder",
								args: data,
							});
						},
						__("Enter folder name"),
						__("Create")
					);
				},
			},
			{
				label: __("Import Zip"),
				action: () => {
					new frappe.ui.FileUploader({
						folder: this.current_folder,
						restrictions: {
							allowed_file_types: [".zip"],
						},
						on_success: (file) => {
							frappe.show_alert(__("Unzipping files..."));
							frappe
								.call("frappe.core.api.file.unzip_file", {
									name: file.name,
								})
								.then((r) => {
									if (r.message) {
										frappe.show_alert(__("Unzipped {0} files", [r.message]));
									}
								});
						},
					});
				},
			},
		];
	}

	add_file_action_buttons() {
		this.$cut_button = this.page
			.add_button(__("Cut"), () => {
				frappe.file_manager.cut(this.get_checked_items(), this.current_folder);
				this.$checks.parents(".file-wrapper").addClass("cut");
			})
			.hide();

		this.$paste_btn = this.page
			.add_button(__("Paste"), () => frappe.file_manager.paste(this.current_folder))
			.hide();

		this.page.add_actions_menu_item(__("Export as zip"), () => {
			let docnames = this.get_checked_items(true);
			if (docnames.length) {
				open_url_post("/api/method/frappe.core.api.file.zip_files", {
					files: JSON.stringify(docnames),
				});
			}
		});
	}

	set_fields() {
		this.fields = this.meta.fields
			.filter((df) => frappe.model.is_value_type(df.fieldtype) && !df.hidden)
			.map((df) => df.fieldname)
			.concat(["name", "modified", "creation"]);
	}

	prepare_data(data) {
		super.prepare_data(data);

		this.data = this.data.map((d) => this.prepare_datum(d));

		// Bring folders to the top
		const { sort_by } = this.sort_selector;
		if (sort_by === "file_name") {
			this.data.sort((a, b) => {
				if (a.is_folder && !b.is_folder) {
					return -1;
				}
				if (!a.is_folder && b.is_folder) {
					return 1;
				}
				return 0;
			});
		}
	}

	prepare_datum(d) {
		let icon_class = "";
		let type = "";
		let title;

		if (d.is_folder) {
			icon_class = "folder-normal";
			type = "folder";
		} else if (frappe.utils.is_image_file(d.file_name)) {
			icon_class = "image";
			type = "image";
		} else {
			icon_class = "file";
			type = "file";
		}

		if (type === "folder") {
			title = this.get_folder_title(d.file_name);
		} else {
			title = d.file_name || d.file_url;
		}

		title = title.slice(0, 60);
		d._title = title;
		d.icon_class = icon_class;
		d._type = type;

		d.subject_html = `
			${frappe.utils.icon(icon_class)}
			<span>${title}</span>
			${d.is_private ? '<i class="fa fa-lock fa-fw text-warning"></i>' : ""}
		`;
		return d;
	}

	get_folder_title(folder_name) {
		// "Home" and "Attachments" are default folders that are always created in english.
		// So we can and should translate them to the user's language.
		if (["Home", "Attachments"].includes(folder_name)) {
			return __(folder_name);
		} else {
			return folder_name;
		}
	}

	before_render() {
		super.before_render();
		frappe.model.user_settings.save("File", "grid_view", frappe.views.FileView.grid_view);
		this.save_view_user_settings({
			last_folder: this.current_folder,
		});
	}

	render() {
		this.$result.empty().removeClass("file-grid-view");
		if (frappe.views.FileView.grid_view) {
			this.render_grid_view();
		} else {
			super.render();
			this.render_header();
			this.render_count();
		}
	}

	after_render() {}

	render_list() {
		if (frappe.views.FileView.grid_view) {
			this.render_grid_view();
		} else {
			super.render_list();
		}
	}

	render_grid_view() {
		let html = this.data
			.map((d) => {
				const icon_class = d.icon_class + "-large";
				let file_body_html =
					d._type == "image"
						? `<div class="file-image"><img src="${d.file_url}" alt="${d.file_name}"></div>`
						: frappe.utils.icon(icon_class, {
								width: "40px",
								height: "45px",
						  });
				const name = escape(d.name);
				const draggable = d.type == "Folder" ? false : true;
				return `
				<a href="${this.get_route_url(d)}"
					draggable="${draggable}" class="file-wrapper ellipsis" data-name="${name}">
					<div class="file-header">
						<input class="level-item list-row-checkbox hidden-xs" type="checkbox" data-name="${name}">
					</div>
					<div class="file-body">
						${file_body_html}
					</div>
					<div class="file-footer">
						<div class="file-title ellipsis">${d._title}</div>
						<div class="file-creation">${this.get_creation_date(d)}</div>
					</div>
				</a>
			`;
			})
			.join("");

		this.$result.addClass("file-grid-view");
		this.$result.empty().html(
			`<div class="file-grid">
				${html}
			</div>`
		);
	}

	get_breadcrumbs_html() {
		const route = frappe.get_route();
		const folders = route.slice(2);

		return folders
			.map((folder, i) => {
				const title = this.get_folder_title(folder);

				if (i === folders.length - 1) {
					return `<span>${title}</span>`;
				}
				const route = folders.reduce((acc, curr, j) => {
					if (j <= i) {
						acc += "/" + curr;
					}
					return acc;
				}, "/app/file/view");

				return `<a href="${route}">${title}</a>`;
			})
			.join("&nbsp;/&nbsp;");
	}

	get_header_html() {
		const breadcrumbs_html = this.get_breadcrumbs_html();

		let header_selector_html = !frappe.views.FileView.grid_view
			? `<input class="level-item list-check-all hidden-xs" type="checkbox" title="${__(
					"Select All"
			  )}">`
			: "";

		let header_columns_html = !frappe.views.FileView.grid_view
			? `<div class="list-row-col ellipsis hidden-xs">
					<span>${__("Size")}</span>
				</div>
				<div class="list-row-col ellipsis hidden-xs">
					<span>${__("Type")}</span>
				</div>
				<div class="list-row-col ellipsis hidden-xs">
					<span>${__("Created")}</span>
				</div>`
			: "";

		let subject_html = `
			<div class="list-row-col list-subject level">
				${header_selector_html}
				<span class="level-item">${breadcrumbs_html}</span>
			</div>
			${header_columns_html}
		`;

		return this.get_header_html_skeleton(subject_html, '<span class="list-count"></span>');
	}

	get_route_url(file) {
		return file.is_folder ? "/app/List/File/" + file.name : this.get_form_link(file);
	}

	get_creation_date(file) {
		const [date] = file.creation.split(" ");
		let created_on;
		if (date === frappe.datetime.now_date()) {
			created_on = comment_when(file.creation);
		} else {
			created_on = frappe.datetime.str_to_user(date);
		}
		return created_on;
	}

	get_left_html(file) {
		file = this.prepare_datum(file);
		const file_size = file.file_size ? frappe.form.formatters.FileSize(file.file_size) : "";
		const route_url = this.get_route_url(file);

		return `
			<div class="list-row-col ellipsis list-subject level">
				<span class="level-item file-select">
					<input class="list-row-checkbox"
						type="checkbox" data-name="${file.name}">
				</span>
				<span class="level-item  ellipsis" title="${frappe.utils.escape_html(file.file_name)}">
					<a class="ellipsis" href="${route_url}" title="${frappe.utils.escape_html(file.file_name)}">
						${file.subject_html}
					</a>
				</span>
			</div>
			<div class="list-row-col ellipsis hidden-xs text-muted">
				<span>${file_size}</span>
			</div>
			<div class="list-row-col ellipsis hidden-xs text-muted">
				<span>${file.file_type || ""}</span>
			</div>
			<div class="list-row-col ellipsis hidden-xs text-muted">
				<span>${this.get_creation_date(file)}</span>
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

	setup_events() {
		super.setup_events();
		this.setup_drag_events();
	}

	setup_drag_events() {
		this.$result.on("dragstart", ".files .file-wrapper", (e) => {
			e.stopPropagation();
			e.originalEvent.dataTransfer.setData("Text", $(e.currentTarget).attr("data-name"));
			e.target.style.opacity = "0.4";
			frappe.file_manager.cut(
				[{ name: $(e.currentTarget).attr("data-name") }],
				this.current_folder
			);
		});

		this.$result.on(
			"dragover",
			(e) => {
				e.preventDefault();
			},
			false
		);

		this.$result.on("dragend", ".files .file-wrapper", (e) => {
			e.preventDefault();
			e.stopPropagation();
			e.target.style.opacity = "1";
		});

		this.$result.on("drop", (e) => {
			e.stopPropagation();
			e.preventDefault();
			const $el = $(e.target).parents(".file-wrapper");

			let dataTransfer = e.originalEvent.dataTransfer;
			if (!dataTransfer) return;

			if (dataTransfer.files && dataTransfer.files.length > 0) {
				new frappe.ui.FileUploader({
					files: dataTransfer.files,
					folder: this.current_folder,
				});
			} else if (dataTransfer.getData("Text")) {
				if ($el.parents(".folders").length !== 0) {
					const file_name = dataTransfer.getData("Text");
					const folder_name = decodeURIComponent($el.attr("data-name"));
					frappe.file_manager.paste(folder_name);
					frappe.show_alert(`File ${file_name} moved to ${folder_name}`);
				}
			}
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
		const hide_paste_btn =
			!frappe.file_manager.can_paste ||
			frappe.file_manager.old_folder === this.current_folder;
		const hide_cut_btn = !(this.$checks && this.$checks.length > 0);

		this.$paste_btn.toggle(!hide_paste_btn);
		this.$cut_button.toggle(!hide_cut_btn);
	}
};

frappe.views.FileView.grid_view = frappe.get_user_settings("File").grid_view || false;

function redirect_to_home_if_invalid_route() {
	const route = frappe.get_route();
	if (route[2] === "List") {
		// if the user somehow redirects to List/File/List
		// redirect back to Home
		frappe.set_route("List", "File", "Home");
		return true;
	}
	return false;
}
