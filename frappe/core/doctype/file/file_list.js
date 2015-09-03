
frappe.listview_settings['File'] = {
	hide_name_column: true,
	use_route: true,
	add_fields: ["is_folder", "file_name"],
	formatters: {
		file_size: function(value) {
			// formatter for file size
			if(value > 1048576) {
				value = flt(flt(value) / 1048576, 1) + "M";
			} else if (value > 1024) {
				value = flt(flt(value) / 1024, 1) + "K";
			}
			return value;
		}
	},
	prepare_data: function(data) {
		// set image icons
		if(data.is_folder) {
			data._title = '<i class="icon-folder-close-alt icon-fixed-width"></i> ' + data.file_name;
		} else if(frappe.utils.is_image_file(data.file_name)) {
			data._title = '<i class="icon-picture icon-fixed-width"></i> ' + data.file_name;
		} else {
			data._title = '<i class="icon-file-alt icon-fixed-width"></i> ' + data.file_name;
		}
	},
	onload: function(doclist) {
		doclist.filter_area = doclist.wrapper.find(".show_filters");
		doclist.breadcrumb = $('<ol class="breadcrumb for-file-list"></ol>')
			.insertBefore(doclist.filter_area);
	},
	before_run: function(doclist) {
		var name_filter = doclist.filter_list.get_filter("file_name");
		if(name_filter) {
			doclist.filter_area.removeClass("hide");
			doclist.breadcrumb.addClass("hide");
		} else {
			doclist.filter_area.addClass("hide");
			doclist.breadcrumb.removeClass("hide");
		}
	},
	refresh: function(doclist) {
		// set folder before querying
		var name_filter = doclist.filter_list.get_filter("file_name");

		var folder_filter = doclist.filter_list.get_filter("folder");
		if(folder_filter) {
			folder_filter.remove(true);
		}

		if(name_filter) return;

		var route = frappe.get_route();
		if(route[2]) {
			doclist.current_folder = route.slice(2).join("/");
			doclist.current_folder_name = route.slice(-1)[0];
		}

		if(!doclist.current_folder) {
			doclist.current_folder = frappe.boot.home_folder;
			doclist.current_folder_name = __("Home");
		}

		doclist.filter_list.add_filter("File", "folder", "=", doclist.current_folder, true);
		doclist.dirty = true;

		frappe.utils.set_title(doclist.current_folder_name);
	},
	post_render_item: function(list, row, data) {
		if(data.is_folder) {
			$(row).find(".list-id").attr("href", "#List/File/" + data.name);
		}
	},
	set_file_route: function(name) {
		frappe.set_route(["List", "File"].concat(decodeURIComponent(name).split("/")));
	},
	post_render: function(doclist) {
		frappe.call({
			method: "frappe.core.doctype.file.file.get_breadcrumbs",
			args: {
				folder: doclist.current_folder
			},
			callback: function(r) {
				doclist.breadcrumb.empty();
				if(r.message && r.message.length) {
					$.each(r.message, function(i, folder) {
						$('<li><a href="#List/File/'+folder.name+'">'
							+ folder.file_name+'</a></li>')
							.appendTo(doclist.breadcrumb);
					});
				}
				$('<li class="active">'+ doclist.current_folder_name+'</li>')
					.appendTo(doclist.breadcrumb);
			}
		});
	}
}
