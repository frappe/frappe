frappe.provide("frappe.views");

frappe.views.ListGroupBy = class ListGroupBy {
	constructor(opts) {
		$.extend(this, opts);
		this.make_wrapper();

		this.user_settings = frappe.get_user_settings(this.doctype);
		this.group_by_fields = ["assigned_to", "owner"];
		if (this.user_settings.group_by_fields) {
			this.group_by_fields = this.group_by_fields.concat(this.user_settings.group_by_fields);
		}
		this.render_group_by_items();
		this.make_group_by_fields_modal();
		this.setup_dropdown();
		this.setup_filter_by();
	}

	make_group_by_fields_modal() {
		let d = new frappe.ui.Dialog({
			title: __("Select Filters"),
			fields: this.get_group_by_dropdown_fields(),
		});

		d.set_primary_action(__("Save"), ({ group_by_fields }) => {
			frappe.model.user_settings.save(
				this.doctype,
				"group_by_fields",
				group_by_fields || null
			);
			this.group_by_fields = group_by_fields
				? ["assigned_to", "owner", ...group_by_fields]
				: ["assigned_to", "owner"];
			this.render_group_by_items();
			this.setup_dropdown();
			d.hide();
		});

		d.$body.prepend(`
			<div class="filters-search">
				<input type="text"
					placeholder="${__("Search")}"
					data-element="search" class="form-control input-xs">
			</div>
		`);

		this.page.sidebar.find(".add-list-group-by a").on("click", () => {
			frappe.utils.setup_search(d.$body, ".unit-checkbox", ".label-area");
			d.show();
		});
	}

	make_wrapper() {
		this.$wrapper = this.sidebar.sidebar.find(".list-group-by");
		let html = `
			<div class="list-group-by-fields">
			</div>
			<div class="add-list-group-by sidebar-action">
				<a class="add-group-by">
					${__("Edit Filters")}
				</a>
			</div>
		`;
		this.$wrapper.html(html);
	}

	render_group_by_items() {
		let get_item_html = (fieldname) => {
			let label, fieldtype;
			if (fieldname === "assigned_to") {
				label = __("Assigned To");
			} else if (fieldname === "owner") {
				label = __("Created By");
			} else {
				label = frappe.meta.get_label(this.doctype, fieldname);
				let docfield = frappe.meta.get_docfield(this.doctype, fieldname);
				if (!docfield) {
					return;
				}
				fieldtype = docfield.fieldtype;
			}

			return `<div class="group-by-field list-link">
						<a class="btn btn-default btn-sm list-sidebar-button" data-toggle="dropdown"
						aria-haspopup="true" aria-expanded="false"
						data-label="${label}" data-fieldname="${fieldname}" data-fieldtype="${fieldtype}"
						href="#" onclick="return false;">
							<span class="ellipsis">${__(label)}</span>
							<span>${frappe.utils.icon("select", "xs")}</span>
						</a>
					<ul class="dropdown-menu group-by-dropdown" role="menu">
					</ul>
			</div>`;
		};
		let html = this.group_by_fields.map(get_item_html).join("");
		this.$wrapper.find(".list-group-by-fields").html(html);
	}

	setup_dropdown() {
		this.$wrapper.find(".group-by-field").on("show.bs.dropdown", (e) => {
			let $dropdown = $(e.currentTarget).find(".group-by-dropdown");
			this.set_loading_state($dropdown);
			let fieldname = $(e.currentTarget).find("a").attr("data-fieldname");
			let fieldtype = $(e.currentTarget).find("a").attr("data-fieldtype");
			this.get_group_by_count(fieldname).then((field_count_list) => {
				if (field_count_list.length) {
					let applied_filter = this.list_view.get_filter_value(
						fieldname == "assigned_to" ? "_assign" : fieldname
					);
					this.render_dropdown_items(
						field_count_list,
						fieldtype,
						$dropdown,
						applied_filter
					);
					this.setup_search($dropdown);
				} else {
					this.set_empty_state($dropdown);
				}
			});
		});
	}

	set_loading_state($dropdown) {
		$dropdown.html(`<li>
			<div class="empty-state group-by-loading">
				${__("Loading...")}
			</div>
		</li>`);
	}

	set_empty_state($dropdown) {
		$dropdown.html(
			`<div class="empty-state group-by-empty">
				${__("No filters found")}
			</div>`
		);
	}

	setup_search($dropdown) {
		frappe.utils.setup_search($dropdown, ".group-by-item", ".group-by-value", "data-name");
	}

	get_group_by_dropdown_fields() {
		let group_by_fields = [];
		let fields = this.list_view.meta.fields.filter((f) =>
			["Select", "Link", "Data", "Int", "Check"].includes(f.fieldtype)
		);
		group_by_fields.push({
			label: __(this.doctype),
			fieldname: "group_by_fields",
			fieldtype: "MultiCheck",
			columns: 2,
			options: fields.map((df) => ({
				label: __(df.label, null, df.parent),
				value: df.fieldname,
				checked: this.group_by_fields.includes(df.fieldname),
			})),
		});
		return group_by_fields;
	}

	get_group_by_count(field) {
		let current_filters = this.list_view.get_filters_for_args();

		// remove filter of the current field
		current_filters = current_filters.filter(
			(f_arr) => !f_arr.includes(field === "assigned_to" ? "_assign" : field)
		);

		let args = {
			doctype: this.doctype,
			current_filters: current_filters,
			field: field,
		};

		return frappe.call("frappe.desk.listview.get_group_by_count", args).then((r) => {
			let field_counts = r.message || [];
			field_counts = field_counts.filter((f) => f.count !== 0);
			let current_user = field_counts.find((f) => f.name === frappe.session.user);
			field_counts = field_counts.filter(
				(f) => !["Guest", "Administrator", frappe.session.user].includes(f.name)
			);
			// Set frappe.session.user on top of the list
			if (current_user) field_counts.unshift(current_user);
			return field_counts;
		});
	}

	render_dropdown_items(fields, fieldtype, $dropdown, applied_filter) {
		let standard_html = `
			<div class="dropdown-search">
				<input type="text"
					placeholder="${__("Search")}"
					data-element="search"
					class="dropdown-search-input form-control input-xs"
				>
			</div>
		`;
		let applied_filter_html = "";
		let dropdown_items_html = "";

		fields.map((field) => {
			if (field.name === applied_filter) {
				applied_filter_html = this.get_dropdown_html(field, fieldtype, true);
			} else {
				dropdown_items_html += this.get_dropdown_html(field, fieldtype);
			}
		});

		let dropdown_html = standard_html + applied_filter_html + dropdown_items_html;
		$dropdown.toggleClass("has-selected", Boolean(applied_filter_html));
		$dropdown.html(dropdown_html);
	}

	get_dropdown_html(field, fieldtype, applied = false) {
		let label;
		if (field.name == null) {
			label = __("Not Set");
		} else if (field.name === frappe.session.user) {
			label = __("Me");
		} else if (fieldtype && fieldtype == "Check") {
			label = field.name == "0" ? __("No") : __("Yes");
		} else if (fieldtype && fieldtype == "Link" && field.title) {
			label = __(field.title);
		} else {
			label = __(field.name);
		}
		let value = field.name == null ? "" : encodeURIComponent(field.name);
		let applied_html = applied
			? `<span class="applied"> ${frappe.utils.icon("tick", "xs")} </span>`
			: "";
		return `<div class="group-by-item ${applied ? "selected" : ""}" data-value="${value}">
			<a class="dropdown-item" href="#" onclick="return false;">
				${applied_html}
				<span class="group-by-value ellipsis" data-name="${field.name}">${label}</span>
				<span class="group-by-count">${field.count}</span>
			</a>
		</div>`;
	}

	setup_filter_by() {
		this.$wrapper.on("click", ".group-by-item", (e) => {
			let $target = $(e.currentTarget);
			let is_selected = $target.hasClass("selected");

			let fieldname = $target.parents(".group-by-field").find("a").data("fieldname");
			let value =
				typeof $target.data("value") === "string"
					? decodeURIComponent($target.data("value").trim())
					: $target.data("value");
			fieldname = fieldname === "assigned_to" ? "_assign" : fieldname;

			return this.list_view.filter_area.remove(fieldname).then(() => {
				if (is_selected) return;
				return this.apply_filter(fieldname, value);
			});
		});
	}

	apply_filter(fieldname, value) {
		let operator = "=";
		if (value === "") {
			operator = "is";
			value = "not set";
		}
		if (fieldname === "_assign") {
			operator = "like";
			value = `%${value}%`;
		}
		return this.list_view.filter_area.add(this.doctype, fieldname, operator, value);
	}
};
