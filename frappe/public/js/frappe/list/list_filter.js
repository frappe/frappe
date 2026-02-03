frappe.provide("frappe.ui");

export default class ListFilter {
	constructor(list_view) {
		this.list_view = list_view;

		Object.assign(this, arguments[0]);
		this.can_add_global = frappe.user.has_role(["System Manager", "Administrator"]);
		this.filters = [];
		this.active_filter = null;
		this.refresh_list_filter();
	}

	refresh_list_filter() {
		if (frappe.is_mobile()) return;
		this.get_list_filters().then(() => {
			this.render_saved_filters();
		});
		this.saved_filters_btn = this.list_view.page.add_inner_button(
			__("Filters"),
			[],
			__("Saved Filters")
		);

		// Clear active filter on clicking 'x' button
		const filter_x_btn = $(".filter-x-button");
		filter_x_btn.on("click", () => {
			this.active_filter = null;
			this.update_active_filter_label("Saved Filters");
		});
	}

	render_saved_filters() {
		const $menu = this.saved_filters_btn.parent();
		$menu.empty();

		this.filters.forEach((filter) => {
			const $item = this.filter_template(filter);

			// Apply filter
			$item.find(".dropdown-item").on("click", () => {
				this.apply_saved_filter(filter.name, filter.filter_name);
			});

			// Remove filter
			$item.find(".remove-filter").on("click", (e) => {
				e.preventDefault();
				e.stopPropagation();
				this.bind_remove_filter(filter);
			});

			$menu.append($item);
		});

		this.append_create_new_item($menu);
	}

	apply_saved_filter(filter_name, filter_label) {
		this.list_view.filter_area.clear().then(() => {
			this.list_view.filter_area.add(this.get_filters_values(filter_name));
			this.active_filter = filter_label;
			this.update_active_filter_label(this.active_filter);
		});
	}

	update_active_filter_label(label) {
		$(`.inner-group-button[data-label="${encodeURIComponent("Saved Filters")}"] button`)
			.contents()
			.first()[0].textContent = label;
	}

	bind_remove_filter(filter) {
		frappe.confirm(
			__("Are you sure you want to remove the {0} filter?", [filter.filter_name.bold()]),
			() => {
				const name = filter.name;
				const applied_filters = this.get_filters_values(name);
				this.remove_filter(name).then(() => this.refresh_list_filter());
				this.update_active_filter_label("Saved Filters");
				this.list_view.filter_area.remove_filters(applied_filters);
			}
		);
	}

	append_create_new_item($menu) {
		const new_filter = {
			name: "create_new",
			filter_name: "Save Current Filter",
		};

		const $create_item = this.filter_template(new_filter, true);
		$create_item.find(".dropdown-item").on("click", (e) => {
			this.show_create_filter_dialog();
		});
		$menu.append($create_item);
	}

	show_create_filter_dialog() {
		const fields = [
			{
				fieldname: "filter_name",
				label: __("Filter Name"),
				fieldtype: "Data",
				reqd: 1,
				description: __("Press Enter to save"),
			},
		];

		// Conditionally add "Is Global" checkbox
		if (this.can_add_global) {
			fields.push({
				fieldname: "is_global",
				label: __("Is Global"),
				fieldtype: "Check",
				default: 0,
			});
		}
		const dialog = new frappe.ui.Dialog({
			title: __("Create Saved Filter"),
			fields: fields,
			primary_action_label: __("Create"),
			primary_action: (values) => {
				this.bind_save_filter(dialog, values.filter_name, values?.is_global);
			},
		});
		dialog.show();
	}

	bind_save_filter(dialog, filter_name, is_global) {
		const value = filter_name;
		const has_value = Boolean(value);
		if (!has_value) {
			return;
		}

		if (this.filter_name_exists(value)) {
			$(dialog.fields_dict.filter_name.wrapper).addClass("has-error");
			dialog.fields_dict.filter_name.set_description(__("Duplicate Filter Name"));
			return;
		}
		this.save_filter(value, is_global).then(() => {
			this.refresh_list_filter();
			dialog.hide();
		});
	}

	save_filter(filter_name, is_global) {
		return frappe.db.insert({
			doctype: "List Filter",
			reference_doctype: this.list_view.doctype,
			filter_name,
			for_user: is_global ? "" : frappe.session.user,
			filters: JSON.stringify(this.get_current_filters()),
		});
	}

	filter_template(filter, add_new = false) {
		return $(`
			<li class="saved-filter-item" data-name="${filter.name}">
				<a class="dropdown-item d-flex justify-content-between align-items-center">
					<span class="filter-label">
						${frappe.utils.escape_html(__(filter.filter_name))}
					</span>
					<span class="remove-filter ${add_new ? "d-none" : ""} ">
						${frappe.utils.icon("x", "sm")}
					</span>
				</a>
			</li>
		`);
	}

	remove_filter(name) {
		if (!name) return;
		return frappe.db.delete_doc("List Filter", name);
	}

	get_filters_values(name) {
		const filter = this.filters.find((filter) => filter.name === name);
		return JSON.parse(filter.filters || "[]");
	}

	get_current_filters() {
		return this.list_view.filter_area.get();
	}

	filter_name_exists(filter_name) {
		return (this.filters || []).find((f) => f.filter_name === filter_name);
	}

	get_list_filters() {
		if (frappe.session.user === "Guest") return Promise.resolve();
		return frappe.db
			.get_list("List Filter", {
				fields: ["name", "filter_name", "for_user", "filters"],
				filters: { reference_doctype: this.list_view.doctype },
				or_filters: [
					["for_user", "=", frappe.session.user],
					["for_user", "=", ""],
				],
				order_by: "filter_name asc",
			})
			.then((filters) => {
				this.filters = filters || [];
			});
	}
}
