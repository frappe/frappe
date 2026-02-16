// List View Selector - Manages saved list views per user/public
frappe.provide("frappe.views");

export default class ListViewSelector {
	constructor({ list_view, doctype }) {
		this.list_view = list_view;
		this.doctype = doctype;
		this.views = { private: [], public: [] };
		this.current_view = null;
		this.setup();
	}

	async setup() {
		await this.fetch_views();
		await this.check_default_view();
		this.render_view_selector();
	}

	async fetch_views() {
		const response = await frappe.call({
			method: "frappe.desk.doctype.user_saved_list_view.user_saved_list_view.get_views",
			args: { doctype: this.doctype },
		});
		this.views = response.message || { private: [], public: [] };
	}

	async check_default_view() {
		const response = await frappe.call({
			method: "frappe.desk.doctype.user_saved_list_view.user_saved_list_view.get_default_view",
			args: { doctype: this.doctype },
		});
		const default_view = response.message;
		
		if (default_view) {
			// Load the default view on initial load
			await this.apply_view(default_view, true);
		}
	}

	render_view_selector() {
		// Add the views dropdown to the page
		this.$views_dropdown = this.list_view.page.add_inner_button(
			__("Views"),
			[],
			__("Saved Views")
		);

		this.refresh_dropdown();
	}

	refresh_dropdown() {
		const $menu = this.$views_dropdown.parent();
		$menu.empty();

		// Default view option
		$menu.append(this.create_menu_item({
			label: __("Default View"),
			is_default: true,
			action: () => this.reset_to_default(),
		}));

		if (this.views.private.length || this.views.public.length) {
			$menu.append('<div class="dropdown-divider"></div>');
		}

		// Private views section
		if (this.views.private.length) {
			$menu.append(`<h6 class="dropdown-header">${__("My Views")}</h6>`);
			this.views.private.forEach((view) => {
				$menu.append(this.create_view_item(view, false));
			});
		}

		// Public views section
		if (this.views.public.length) {
			$menu.append(`<h6 class="dropdown-header">${__("Public Views")}</h6>`);
			this.views.public.forEach((view) => {
				$menu.append(this.create_view_item(view, true));
			});
		}

		$menu.append('<div class="dropdown-divider"></div>');

		// Save current view option
		$menu.append(this.create_menu_item({
			label: __("Save Current View"),
			icon: "add",
			action: () => this.show_save_dialog(),
		}));

		// Save as new view option (if current view is selected)
		if (this.current_view) {
			$menu.append(this.create_menu_item({
				label: __("Save as New View"),
				icon: "copy",
				action: () => this.show_save_dialog(true),
			}));

			$menu.append(this.create_menu_item({
				label: __("Update Current View"),
				icon: "refresh",
				action: () => this.update_current_view(),
			}));
		}
	}

	create_menu_item({ label, icon, action, is_default }) {
		const icon_html = icon ? frappe.utils.icon(icon, "sm") : "";
		const $item = $(`
			<a class="dropdown-item" href="#">
				${icon_html}
				<span class="menu-item-label">${label}</span>
			</a>
		`);
		$item.on("click", (e) => {
			e.preventDefault();
			action();
		});
		return $item;
	}

	create_view_item(view, is_public) {
		const is_current = this.current_view === view.name;
		const can_delete = !is_public || frappe.user.has_role("System Manager");
		const can_set_default = true;

		const $item = $(`
			<div class="dropdown-item view-item d-flex align-items-center justify-content-between ${is_current ? "active" : ""}" data-view="${view.name}">
				<a href="#" class="view-name grow">${view.view_name}</a>
				<span class="view-actions">
					${can_set_default ? `<a href="#" class="set-default-btn ml-2" title="${__("Set as Default")}">
						${frappe.utils.icon("star", "sm")}
					</a>` : ""}
					${can_delete ? `<a href="#" class="delete-view-btn ml-2 text-danger" title="${__("Delete")}">
						${frappe.utils.icon("delete", "sm")}
					</a>` : ""}
				</span>
			</div>
		`);

		$item.find(".view-name").on("click", (e) => {
			e.preventDefault();
			e.stopPropagation();
			this.apply_view(view.name);
		});

		$item.find(".set-default-btn").on("click", (e) => {
			e.preventDefault();
			e.stopPropagation();
			this.set_as_default(view.name, view.view_name);
		});

		$item.find(".delete-view-btn").on("click", (e) => {
			e.preventDefault();
			e.stopPropagation();
			this.delete_view(view.name, view.view_name);
		});

		return $item;
	}

	async apply_view(view_name, silent = false) {
		try {
			const response = await frappe.call({
				method: "frappe.desk.doctype.user_saved_list_view.user_saved_list_view.get_view",
				args: { name: view_name },
			});

			const view = response.message;
			if (!view) return;

			this.current_view = view_name;
			this.current_view_data = view;

			// Apply columns - build columns array directly
			if (view.columns) {
				const saved_columns = JSON.parse(view.columns);
				this.list_view.list_view_settings.fields = JSON.stringify(saved_columns);
				
				// Build columns array directly from saved view
				this.apply_saved_columns(saved_columns);
			}

			// Apply filters
			if (view.filters) {
				const filters = JSON.parse(view.filters);
				await this.list_view.filter_area.clear(false);
				if (filters.length) {
					await this.list_view.filter_area.add(filters);
				}
			}

			// Apply sorting
			if (view.sort_by) {
				this.list_view.sort_by = view.sort_by;
				this.list_view.sort_order = view.sort_order || "desc";
				this.list_view.sort_selector?.set_value(view.sort_by, view.sort_order);
			}

			// Apply list view settings
			const settings = {
				disable_count: view.disable_count,
				disable_auto_refresh: view.disable_auto_refresh,
				disable_sidebar_stats: view.disable_sidebar_stats,
				disable_automatic_recency_filters: view.disable_automatic_recency_filters,
				disable_comment_count: view.disable_comment_count,
				disable_scrolling: view.disable_scrolling,
				allow_edit: view.allow_edit,
				show_tags: view.show_tags,
			};
			Object.assign(this.list_view.list_view_settings, settings);

			// Refresh the list and re-render header
			await this.list_view.refresh(true);

			// Update dropdown label
			this.update_dropdown_label(view.view_name);
			this.refresh_dropdown();

			if (!silent) {
				frappe.show_alert({
					message: __("View '{0}' applied", [view.view_name]),
					indicator: "green",
				});
			}
		} catch (e) {
			console.error("Error applying view:", e);
			frappe.show_alert({
				message: __("Error applying view"),
				indicator: "red",
			});
		}
	}

	apply_saved_columns(saved_columns) {
		// Build columns array directly from saved view
		const list_view = this.list_view;
		const get_df = frappe.meta.get_docfield.bind(null, this.doctype);
		
		// Start with empty columns
		list_view.columns = [];
		
		// Add title field first (always first column)
		if (list_view.meta.title_field) {
			list_view.columns.push({
				type: "Subject",
				df: get_df(list_view.meta.title_field),
			});
		} else {
			list_view.columns.push({
				type: "Subject",
				df: {
					label: __("ID"),
					fieldname: "name",
				},
			});
		}
		
		// Add Tag column (normally hidden)
		list_view.columns.push({
			type: "Tag",
		});
		
		// Add columns from saved view
		for (const field of saved_columns) {
			// Skip subject field (already added)
			if (field.fieldname === list_view.meta.title_field) continue;
			if (field.fieldname === "name" && !list_view.meta.title_field) continue;
			
			// Handle status field
			if (field.fieldname === "status_field") {
				if (frappe.has_indicator(this.doctype)) {
					list_view.columns.push({
						type: "Status",
					});
				}
				continue;
			}
			
			// Get field definition from meta
			const df = get_df(field.fieldname);
			if (df) {
				list_view.columns.push({
					type: "Field",
					df: df,
				});
			} else if (field.fieldname === "name") {
				// Handle ID field
				list_view.columns.push({
					type: "Field",
					df: {
						label: __("ID"),
						fieldname: "name",
					},
				});
			}
		}
		
		// Limit columns
		list_view.columns = list_view.columns.slice(0, list_view.max_number_of_fields);
		
		// Re-render header with new columns
		list_view.render_header(true);
	}

	reset_to_default() {
		this.current_view = null;
		this.current_view_data = null;

		// Clear filters
		this.list_view.filter_area.clear();

		// Reset sorting
		this.list_view.sort_by = this.list_view.meta.sort_field || "creation";
		this.list_view.sort_order = this.list_view.meta.sort_order || "desc";

		// Reset columns
		this.list_view.list_view_settings.fields = null;

		// Reset list view settings to default
		frappe.call({
			method: "frappe.desk.listview.get_list_settings",
			args: { doctype: this.doctype },
		}).then((response) => {
			this.list_view.list_view_settings = response.message || {};
			this.list_view.setup_columns();
			this.list_view.refresh(true);
		});

		this.update_dropdown_label(__("Saved Views"));
		this.refresh_dropdown();

		frappe.show_alert({
			message: __("Reset to default view"),
			indicator: "blue",
		});
	}

	update_dropdown_label(label) {
		const $btn = $(`.inner-group-button[data-label="${encodeURIComponent("Saved Views")}"] button`);
		$btn.contents().first()[0].textContent = label;
	}

	show_save_dialog(save_as_new = false) {
		const fields = [
			{
				fieldname: "view_name",
				label: __("View Name"),
				fieldtype: "Data",
				reqd: 1,
				default: save_as_new ? "" : (this.current_view_data?.view_name || ""),
			},
		];

		// Add is_public option for System Managers
		if (frappe.user.has_role("System Manager")) {
			fields.push({
				fieldname: "is_public",
				label: __("Public View"),
				fieldtype: "Check",
				description: __("Public views are visible to all users"),
				default: save_as_new ? 0 : (this.current_view_data?.is_public || 0),
			});
		}

		const dialog = new frappe.ui.Dialog({
			title: save_as_new ? __("Save as New View") : __("Save View"),
			fields: fields,
			primary_action_label: __("Save"),
			primary_action: async (values) => {
				await this.save_view(
					values.view_name,
					values.is_public || 0,
					save_as_new ? null : this.current_view
				);
				dialog.hide();
			},
		});
		dialog.show();
	}

	async save_view(view_name, is_public, view_id = null) {
		// Gather current state
		const columns = this.get_current_columns();
		const filters = this.get_current_filters();
		const sort_by = this.list_view.sort_by;
		const sort_order = this.list_view.sort_order;
		const settings = this.get_current_settings();

		try {
			const response = await frappe.call({
				method: "frappe.desk.doctype.user_saved_list_view.user_saved_list_view.save_view",
				args: {
					doctype: this.doctype,
					view_name: view_name,
					columns: JSON.stringify(columns),
					filters: JSON.stringify(filters),
					sort_by: sort_by,
					sort_order: sort_order,
					settings: JSON.stringify(settings),
					is_public: is_public,
					view_id: view_id,
				},
			});

			if (response.message) {
				this.current_view = response.message.name;
				await this.fetch_views();
				this.refresh_dropdown();
				this.update_dropdown_label(view_name);

				frappe.show_alert({
					message: __("View '{0}' saved", [view_name]),
					indicator: "green",
				});
			}
		} catch (e) {
			console.error("Error saving view:", e);
			frappe.show_alert({
				message: __("Error saving view"),
				indicator: "red",
			});
		}
	}

	async update_current_view() {
		if (!this.current_view || !this.current_view_data) {
			frappe.show_alert({
				message: __("No view selected to update"),
				indicator: "orange",
			});
			return;
		}

		await this.save_view(
			this.current_view_data.view_name,
			this.current_view_data.is_public,
			this.current_view
		);
	}

	get_current_columns() {
		// Get current columns from list view
		if (this.list_view.list_view_settings?.fields) {
			return JSON.parse(this.list_view.list_view_settings.fields);
		}

		// Fallback to default columns from list view
		return this.list_view.columns
			.filter((col) => col.type === "Field" || col.type === "Subject" || col.type === "Status")
			.map((col) => {
				if (col.type === "Status") {
					return { fieldname: "status_field", label: __("Status") };
				}
				return {
					fieldname: col.df?.fieldname || col.fieldname,
					label: col.df?.label || col.label,
				};
			});
	}

	get_current_filters() {
		return this.list_view.filter_area?.get() || [];
	}

	get_current_settings() {
		const settings = this.list_view.list_view_settings || {};
		return {
			disable_count: settings.disable_count || 0,
			disable_auto_refresh: settings.disable_auto_refresh || 0,
			disable_sidebar_stats: settings.disable_sidebar_stats || 0,
			disable_automatic_recency_filters: settings.disable_automatic_recency_filters || 0,
			disable_comment_count: settings.disable_comment_count || 0,
			disable_scrolling: settings.disable_scrolling || 0,
			allow_edit: settings.allow_edit || 0,
			show_tags: settings.show_tags || 0,
		};
	}

	async set_as_default(view_name, view_label) {
		try {
			await frappe.call({
				method: "frappe.desk.doctype.user_saved_list_view.user_saved_list_view.set_default_view",
				args: {
					doctype: this.doctype,
					view_name: view_name,
				},
			});

			frappe.show_alert({
				message: __("'{0}' set as default view", [view_label]),
				indicator: "green",
			});
		} catch (e) {
			console.error("Error setting default view:", e);
		}
	}

	async delete_view(view_name, view_label) {
		frappe.confirm(
			__("Are you sure you want to delete the view '{0}'?", [view_label]),
			async () => {
				try {
					await frappe.call({
						method: "frappe.desk.doctype.user_saved_list_view.user_saved_list_view.delete_view",
						args: { name: view_name },
					});

					// Reset to default if deleted view was current
					if (this.current_view === view_name) {
						this.reset_to_default();
					}

					await this.fetch_views();
					this.refresh_dropdown();

					frappe.show_alert({
						message: __("View '{0}' deleted", [view_label]),
						indicator: "green",
					});
				} catch (e) {
					console.error("Error deleting view:", e);
					frappe.show_alert({
						message: __("Error deleting view"),
						indicator: "red",
					});
				}
			}
		);
	}
}
