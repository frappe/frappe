//TODO

// show breadcrumbs
// search bar to add search filter
// back button
// new
	// if file, attach
	// if folder, set name

frappe.listview_settings['File'] = {
	hide_name_column: true,
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
		doclist.breadcrumb = $('<ol class="breadcrumb"></ol>')
			.insertBefore(doclist.wrapper.find(".show_filters"));
	},
	refresh: function(doclist) {
		// set folder before querying
		var name_filter = doclist.filter_list.get_filter("name");

		var folder_filter = doclist.filter_list.get_filter("folder");
		if(folder_filter) {
			folder_filter.remove(true);
		}

		if(name_filter) return;

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
			$(row).find(".list-id").on("click", function() {
				list.doclistview.current_folder = data.name;
				list.doclistview.current_folder_name = data.file_name;
				list.doclistview.refresh();
				return false;
			});
		}
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
						$('<li><a href="#">'+ folder.file_name+'</a></li>')
							.appendTo(doclist.breadcrumb)
							.attr("name", folder.name)
							.attr("file_name", folder.file_name)
							.on("click", function() {
								doclist.current_folder = $(this).attr("name");
								doclist.current_folder_name = $(this).attr("file_name");
								doclist.refresh();
								return false;
							});
					});
				}
				$('<li class="active">'+ doclist.current_folder_name+'</li>')
					.appendTo(doclist.breadcrumb);
			}
		});
	}
}
