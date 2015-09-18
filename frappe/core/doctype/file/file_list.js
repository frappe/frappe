frappe.provide("frappe.ui");

frappe.listview_settings['File'] = {
	hide_name_column: true,
	use_route: true,
	add_fields: ["is_folder", "file_name", "file_url", "folder"],
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
			data._title = '<i class="icon-file-alt icon-fixed-width"></i> \
				' + (data.file_name ? data.file_name : data.file_url);
		}
	},
	onload: function(doclist) {
		doclist.filter_area = doclist.wrapper.find(".show_filters");

		doclist.breadcrumb = $('<ol class="breadcrumb for-file-list"></ol>')
			.insertBefore(doclist.filter_area);

		doclist.listview.settings.setup_menu(doclist);
		doclist.listview.settings.setup_dragdrop(doclist);

		doclist.$page.on("click", ".list-delete", function(event) {
				doclist.listview.settings.add_menu_item_copy(doclist);
		})
	},
	list_view_doc:function(doclist){
		$(doclist.wrapper).on("click", 'button[list_view_doc="'+doclist.doctype+'"]', function(){
			dialog = frappe.ui.get_upload_dialog({
				"args": {
					"folder": doclist.current_folder,
					"from_form": 1
				},
				callback: function() {
					doclist.refresh();
				}
			});
		});
	},
	setup_menu: function(doclist) {
		doclist.page.add_menu_item(__("New Folder"), function() {
			var d = frappe.prompt(__("Name"), function(values) {
				if((values.value.indexOf("/") > -1)){
					frappe.throw("Folder name should not include / !!!");
					return;
				}
				var data =  {
					"file_name": values.value,
					"folder": doclist.current_folder
				};
				frappe.call({
					method: "frappe.core.doctype.file.file.create_new_folder",
					args: data,
					callback: function(r) { }
				})
			}, __('Enter folder name'), __("Create"));
		});

		doclist.page.add_menu_item(__("Edit Folder"), function() {
			frappe.set_route("Form", "File", doclist.current_folder);
		});
	},
	setup_dragdrop: function(doclist) {
		$(doclist.$page).on('dragenter dragover', false)
			.on('drop', function (e) {
				var dataTransfer = e.originalEvent.dataTransfer;
				if (!(dataTransfer && dataTransfer.files && dataTransfer.files.length > 0)) {
					return;
				}
				e.stopPropagation();
				e.preventDefault();
				frappe.upload.upload_file(dataTransfer.files[0], {
					"folder": doclist.current_folder,
					"from_form": 1
				}, {});
			});
	},
	add_menu_item_copy: function(doclist){
		if (!doclist.copy) {
			var copy_menu = doclist.page.add_menu_item(__("Copy"), function() {
				if(doclist.$page.find(".list-delete:checked").length){
					doclist.selected_files = doclist.get_checked_items();
					doclist.old_parent = doclist.current_folder;
					doclist.listview.settings.add_menu_item_paste(doclist);
				}
				else{
					frappe.throw("Please select file to copy");
				}
			})
			doclist.copy = true;
		}
	},
	add_menu_item_paste:function(doclist){
		var paste_menu = doclist.page.add_menu_item(__("Paste"), function(){
			frappe.call({
				method:"frappe.core.doctype.file.file.move_file",
				args: {
					"file_list": doclist.selected_files,
					"new_parent": doclist.current_folder,
					"old_parent": doclist.old_parent
				},
				callback:function(r){
					doclist.paste = false;
					frappe.msgprint(__(r.message));
					doclist.selected_files = [];
					$(paste_menu).remove();
				}
			})
		})
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
		doclist.fresh = false;

		doclist.page.set_title(doclist.current_folder_name);
		frappe.utils.set_title(doclist.current_folder_name);
	},
	set_primary_action:function(doclist){
		doclist.page.clear_primary_action();
		doclist.page.set_primary_action(__("New"), function() {
			dialog = frappe.ui.get_upload_dialog({
				"args": {
					"folder": doclist.current_folder,
					"from_form": 1
				},
				callback: function() {
					doclist.refresh();
				}
			});
		}, "octicon octicon-plus");
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
