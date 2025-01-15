frappe.ui.form.MultiSelectDialog = class MultiSelectDialog {
	constructor(opts) {
		/* Options: doctype, target, setters, get_query, action, add_filters_group, data_fields, primary_action_label, columns */
		Object.assign(this, opts);
		this.for_select = this.doctype == "[Select]";
		if (!this.for_select) {
			frappe.model.with_doctype(this.doctype, () => this.init());
		} else {
			this.init();
		}
	}

	init() {
		this.page_length = 20;
		this.child_page_length = 20;
		this.fields = this.get_fields();

		this.make();

		this.selected_fields = new Set();
	}

	get_fields() {
		const primary_fields = this.get_primary_filters();
		const result_fields = this.get_result_fields();
		const data_fields = this.get_data_fields();
		const child_selection_fields = this.get_child_selection_fields();

		return [...primary_fields, ...result_fields, ...data_fields, ...child_selection_fields];
	}

	get_result_fields() {
		const show_next_page = () => {
			this.page_length += 20;
			this.get_results();
		};
		return [
			{
				fieldtype: "HTML",
				fieldname: "results_area",
			},
			{
				fieldtype: "Button",
				fieldname: "more_btn",
				label: __("More"),
				click: show_next_page.bind(this),
			},
		];
	}

	get_data_fields() {
		if (this.data_fields && this.data_fields.length) {
			// Custom Data Fields
			return [{ fieldtype: "Section Break" }, ...this.data_fields];
		} else {
			return [];
		}
	}

	get_child_selection_fields() {
		const fields = [];
		if (this.allow_child_item_selection && this.child_fieldname) {
			const show_more_child_results = () => {
				this.child_page_length += 20;
				this.show_child_results();
			};
			fields.push({ fieldtype: "HTML", fieldname: "child_selection_area" });
			fields.push({
				fieldtype: "Button",
				fieldname: "more_child_btn",
				hidden: 1,
				label: __("More"),
				click: show_more_child_results.bind(this),
			});
		}
		return fields;
	}

	make() {
		let title = __("Select {0}", [this.for_select ? __("value") : __(this.doctype)]);

		this.dialog = new frappe.ui.Dialog({
			title: title,
			fields: this.fields,
			size: this.size,
			primary_action_label: this.primary_action_label || __("Get Items"),
			secondary_action_label: __("Make {0}", [__(this.doctype)]),
			primary_action: () => {
				let filters_data = this.get_custom_filters();
				const data_values = cur_dialog.get_values(); // to pass values of data fields
				const filtered_children = this.get_selected_child_names();
				const selected_documents = [
					...this.get_checked_values(),
					...this.get_parent_name_of_selected_children(),
				];
				this.action(selected_documents, {
					...this.args,
					...data_values,
					...filters_data,
					filtered_children,
				});
			},
			secondary_action: this.make_new_document.bind(this),
		});

		if (this.add_filters_group) {
			this.make_filter_area();
		}

		this.args = {};

		this.setup_results();
		this.bind_events();
		this.get_results();
		this.dialog.show();
	}

	make_new_document(e) {
		// If user wants to close the modal
		if (e) {
			this.set_route_options();
			frappe.new_doc(this.doctype, true);
		}
	}

	set_route_options() {
		// set route options to get pre-filled form fields
		frappe.route_options = {};
		if (Array.isArray(this.setters)) {
			for (let df of this.setters) {
				frappe.route_options[df.fieldname] =
					this.dialog.fields_dict[df.fieldname].get_value() || undefined;
			}
		} else {
			Object.keys(this.setters).forEach((setter) => {
				frappe.route_options[setter] =
					this.dialog.fields_dict[setter].get_value() || undefined;
			});
		}
	}

	setup_results() {
		this.$parent = $(this.dialog.body);
		this.$wrapper = this.dialog.fields_dict.results_area.$wrapper
			.append(`<div class="results my-3"
			style="border: 1px solid #d1d8dd; border-radius: 3px; height: 300px; overflow: auto;"></div>`);

		this.$results = this.$wrapper.find(".results");
		this.$results.append(this.make_list_row());
	}

	show_child_results() {
		this.get_child_result().then((r) => {
			this.child_results = r.message || [];
			this.render_child_datatable();

			this.$wrapper.addClass("hidden");
			this.$child_wrapper.removeClass("hidden");
			this.dialog.fields_dict.more_btn.$wrapper.hide();
		});
	}

	is_child_selection_enabled() {
		return this.dialog.fields_dict["allow_child_item_selection"]?.get_value();
	}

	toggle_child_selection() {
		if (this.is_child_selection_enabled()) {
			this.show_child_results();
		} else {
			this.child_results = [];
			this.get_results();
			this.$wrapper.removeClass("hidden");
			this.$child_wrapper.addClass("hidden");
		}
	}

	render_child_datatable() {
		if (!this.child_datatable) {
			this.setup_child_datatable();
		} else {
			setTimeout(() => {
				this.child_datatable.rowmanager.checkMap = [];
				this.child_datatable.refresh(this.get_child_datatable_rows());
				this.$child_wrapper.find(".dt-scrollable").css("height", "300px");
				this.$child_wrapper.find(".dt-scrollable").css("overflow-y", "scroll");
			}, 500);
		}
	}

	get_child_datatable_columns() {
		const parent = this.doctype;
		return [parent, ...this.child_columns].map((d) => ({
			name: frappe.unscrub(d),
			editable: false,
		}));
	}

	get_child_datatable_rows() {
		if (this.child_results.length > this.child_page_length) {
			this.dialog.fields_dict.more_child_btn.toggle(true);
		} else {
			this.dialog.fields_dict.more_child_btn.toggle(false);
		}
		return this.child_results
			.slice(0, this.child_page_length)
			.map((d) => Object.values(d).slice(1)); // slice name field
	}

	setup_child_datatable() {
		const header_columns = this.get_child_datatable_columns();
		const rows = this.get_child_datatable_rows();
		this.$child_wrapper = this.dialog.fields_dict.child_selection_area.$wrapper;
		this.$child_wrapper.addClass("my-3");

		this.child_datatable = new frappe.DataTable(this.$child_wrapper.get(0), {
			columns: header_columns,
			data: rows,
			layout: "fluid",
			inlineFilters: true,
			serialNoColumn: false,
			checkboxColumn: true,
			cellHeight: 35,
			noDataMessage: __("No Data"),
			disableReorderColumn: true,
		});
		this.$child_wrapper.find(".dt-scrollable").css("height", "300px");
	}

	get_primary_filters() {
		let fields = [];

		let columns = new Array(3);

		// Hack for three column layout
		// To add column break
		columns[0] = [
			{
				fieldtype: "Data",
				label: __("Name"),
				fieldname: "search_term",
			},
		];
		columns[1] = [];
		columns[2] = [];

		if ($.isArray(this.setters)) {
			this.setters.forEach((setter, index) => {
				columns[(index + 1) % 3].push(setter);
			});
		} else {
			Object.keys(this.setters).forEach((setter, index) => {
				let df_prop = frappe.meta.docfield_map[this.doctype][setter];

				// Index + 1 to start filling from index 1
				// Since Search is a standrd field already pushed
				columns[(index + 1) % 3].push({
					fieldtype: df_prop.fieldtype,
					label: df_prop.label,
					fieldname: setter,
					options: df_prop.options,
					read_only:
						(this?.read_only_setters && this.read_only_setters.includes(setter)) || 0,
					default: this.setters[setter],
				});
			});
		}

		// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/seal
		if (Object.seal) {
			Object.seal(columns);
			// now a is a fixed-size array with mutable entries
		}

		if (this.allow_child_item_selection) {
			this.child_doctype = frappe.meta.get_docfield(
				this.doctype,
				this.child_fieldname
			).options;
			columns[0].push({
				fieldtype: "Check",
				label: __("Select {0}", [__(this.child_doctype)]),
				fieldname: "allow_child_item_selection",
				onchange: this.toggle_child_selection.bind(this),
			});
		}

		fields = [
			...columns[0],
			{ fieldtype: "Column Break" },
			...columns[1],
			{ fieldtype: "Column Break" },
			...columns[2],
			{ fieldtype: "Section Break", fieldname: "primary_filters_sb" },
		];

		if (this.add_filters_group) {
			fields.push({
				fieldtype: "HTML",
				fieldname: "filter_area",
			});
		}

		return fields;
	}

	make_filter_area() {
		this.filter_group = new frappe.ui.FilterGroup({
			parent: this.dialog.get_field("filter_area").$wrapper,
			doctype: this.doctype,
			on_change: () => {
				if (this.is_child_selection_enabled()) {
					this.show_child_results();
				} else {
					this.get_results();
				}
			},
		});
		// 'Apply Filter' breaks since the filers are not in a popover
		// Hence keeping it hidden
		this.filter_group.wrapper.find(".apply-filters").hide();
	}

	get_custom_filters() {
		if (this.add_filters_group && this.filter_group) {
			return this.filter_group.get_filters().reduce((acc, filter) => {
				return Object.assign(acc, {
					[filter[1]]: [filter[2], filter[3]],
				});
			}, {});
		} else {
			return {};
		}
	}

	bind_events() {
		let me = this;

		this.$results.on("click", ".list-item-container", function (e) {
			if (!$(e.target).is(":checkbox") && !$(e.target).is("a")) {
				$(this).find(":checkbox").trigger("click");
			}
			let name = $(this).attr("data-item-name").trim();
			if ($(this).find(":checkbox").is(":checked")) {
				me.selected_fields.add(name);
			} else {
				me.selected_fields.delete(name);
			}
		});

		this.$results.on("click", ".list-item--head :checkbox", (e) => {
			let checked = $(e.target).is(":checked");
			this.$results.find(".list-item-container .list-row-check").each(function () {
				$(this).prop("checked", checked);
				const name = $(this).closest(".list-item-container").attr("data-item-name").trim();
				if (checked) {
					me.selected_fields.add(name);
				} else {
					me.selected_fields.delete(name);
				}
			});
		});

		this.$parent.find(".input-with-feedback").on("change", () => {
			frappe.flags.auto_scroll = false;
			if (this.is_child_selection_enabled()) {
				this.show_child_results();
			} else {
				this.get_results();
			}
		});

		this.$parent.find('[data-fieldtype="Data"]').on("input", () => {
			var $this = $(this);
			clearTimeout($this.data("timeout"));
			$this.data(
				"timeout",
				setTimeout(function () {
					frappe.flags.auto_scroll = false;
					if (me.is_child_selection_enabled()) {
						me.show_child_results();
					} else {
						me.empty_list();
						me.get_results();
					}
				}, 300)
			);
		});
	}

	get_parent_name_of_selected_children() {
		if (!this.child_datatable || !this.child_datatable.datamanager.rows.length) return [];

		let parent_names = this.child_datatable.rowmanager.checkMap.reduce(
			(parent_names, checked, index) => {
				if (checked == 1) {
					const parent_name = this.child_results[index].parent;
					if (!parent_names.includes(parent_name)) {
						parent_names.push(parent_name);
					}
				}
				return parent_names;
			},
			[]
		);

		return parent_names;
	}

	get_selected_child_names() {
		if (!this.child_datatable || !this.child_datatable.datamanager.rows.length) return [];

		let checked_names = this.child_datatable.rowmanager.checkMap.reduce(
			(checked_names, checked, index) => {
				if (checked == 1) {
					const child_row_name = this.child_results[index].name;
					checked_names.push(child_row_name);
				}
				return checked_names;
			},
			[]
		);

		return checked_names;
	}

	get_checked_values() {
		// Return name of checked value.
		return this.$results
			.find(".list-item-container")
			.map(function () {
				if ($(this).find(".list-row-check:checkbox:checked").length > 0) {
					return $(this).attr("data-item-name");
				}
			})
			.get();
	}

	get_checked_items() {
		// Return checked items with all the column values.
		let checked_values = this.get_checked_values();
		return this.results.filter((res) => checked_values.includes(res.name));
	}

	get_datatable_columns() {
		if (this.get_query && this.get_query().query && this.columns) return this.columns;

		if (Array.isArray(this.setters))
			return ["name", ...this.setters.map((df) => df.fieldname)];

		return ["name", ...Object.keys(this.setters)];
	}

	make_list_row(result = {}) {
		var me = this;
		// Make a head row by default (if result not passed)
		let head = Object.keys(result).length === 0;

		let contents = ``;
		this.get_datatable_columns().forEach(function (column) {
			contents += `<div class="list-item__content ellipsis">
				${
					head
						? `<span class="ellipsis text-muted" title="${__(
								frappe.model.unscrub(column)
						  )}">${__(frappe.model.unscrub(column))}</span>`
						: column !== "name"
						? `<span class="ellipsis result-row" title="${__(
								result[column] || ""
						  )}">${__(result[column] || "")}</span>`
						: `<a href="${
								"/app/" + frappe.router.slug(me.doctype) + "/" + result[column] ||
								""
						  }" class="list-id ellipsis" title="${__(result[column] || "")}">
							${__(result[column] || "")}</a>`
				}
			</div>`;
		});

		let $row = $(`<div class="list-item">
			<div class="list-item__content" style="flex: 0 0 10px;">
				<input type="checkbox" class="list-row-check" data-item-name="${result.name}" ${
			result.checked ? "checked" : ""
		}>
			</div>
			${contents}
		</div>`);

		head
			? $row.addClass("list-item--head")
			: ($row = $(
					`<div class="list-item-container" data-item-name="${result.name}"></div>`
			  ).append($row));

		return $row;
	}

	render_result_list(results, more = 0, empty = true) {
		var me = this;
		var more_btn = me.dialog.fields_dict.more_btn.$wrapper;

		// Make empty result set if filter is set
		if (!frappe.flags.auto_scroll && empty) {
			this.empty_list();
		}
		more_btn.hide();
		$(".modal-dialog .list-item--head").css("z-index", 1);

		if (results.length === 0) return;
		if (more) more_btn.show();

		let checked = this.get_checked_values();

		results
			.filter((result) => !checked.includes(result.name))
			.forEach((result) => {
				me.$results.append(me.make_list_row(result));
			});

		this.$results.find(".list-item--head").css("z-index", 1);

		if (frappe.flags.auto_scroll) {
			this.$results.animate({ scrollTop: me.$results.prop("scrollHeight") }, 500);
		}
	}

	empty_list() {
		// Store all checked items
		let checked = this.results
			.filter((result) => this.selected_fields.has(result.name))
			.map((item) => ({
				...item,
				checked: true,
			}));

		// Remove **all** items
		this.$results.find(".list-item-container").remove();

		// Rerender checked items
		this.render_result_list(checked, 0, false);
	}

	get_filters_from_setters() {
		let me = this;
		let filters = (this.get_query ? this.get_query().filters : {}) || {};
		let filter_fields = [];

		if ($.isArray(this.setters)) {
			for (let df of this.setters) {
				filters[df.fieldname] =
					me.dialog.fields_dict[df.fieldname].get_value() || undefined;
				me.args[df.fieldname] = filters[df.fieldname];
				filter_fields.push(df.fieldname);
			}
		} else {
			Object.keys(this.setters).forEach(function (setter) {
				var value = me.dialog.fields_dict[setter].get_value();
				if (me.dialog.fields_dict[setter].df.fieldtype == "Data" && value) {
					filters[setter] = ["like", "%" + value + "%"];
				} else {
					filters[setter] = value || undefined;
					me.args[setter] = filters[setter];
					filter_fields.push(setter);
				}
			});
		}

		return [filters, filter_fields];
	}

	get_args_for_search() {
		let [filters, filter_fields] = this.get_filters_from_setters();

		let custom_filters = this.get_custom_filters();
		Object.assign(filters, custom_filters);

		return {
			doctype: this.doctype,
			txt: this.dialog.fields_dict["search_term"].get_value(),
			filters: filters,
			filter_fields: filter_fields,
			page_length: this.page_length + 5,
			query: this.get_query ? this.get_query().query : "",
			as_dict: 1,
		};
	}

	async perform_search(args) {
		const res = await frappe.call({
			type: "GET",
			method: "frappe.desk.search.search_widget",
			no_spinner: true,
			args: args,
		});
		const more = res.message.length && res.message.length > this.page_length ? 1 : 0;

		return [res.message, more];
	}

	async get_results() {
		const args = this.get_args_for_search();
		let [results, more] = await this.perform_search(args);

		if (more) {
			results = results.splice(0, this.page_length);
		}

		this.results = [];
		if (results.length) {
			results.forEach((result) => {
				result.checked = 0;
				this.results.push(result);
			});
		}
		this.render_result_list(this.results, more);
	}

	async get_filtered_parents_for_child_search() {
		const parent_search_args = this.get_args_for_search();
		parent_search_args.filter_fields = ["name"];
		const [results, _] = await this.perform_search(parent_search_args);

		let parent_names = [];
		if (results.length) {
			parent_names = results.map((v) => v.name);
		}
		return parent_names;
	}

	async add_parent_filters(filters) {
		const parent_names = await this.get_filtered_parents_for_child_search();
		if (parent_names.length) {
			filters.push(["parent", "in", parent_names]);
		}
	}

	add_custom_child_filters(filters) {
		if (this.add_filters_group && this.filter_group) {
			this.filter_group.get_filters().forEach((filter) => {
				if (filter[0] == this.child_doctype) {
					filters.push([filter[1], filter[2], filter[3]]);
				}
			});
		}
	}

	async get_child_result() {
		let filters = [["parentfield", "=", this.child_fieldname]];

		await this.add_parent_filters(filters);
		this.add_custom_child_filters(filters);

		return frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: this.child_doctype,
				filters: filters,
				fields: ["name", "parent", ...this.child_columns],
				parent: this.doctype,
				limit_page_length: this.child_page_length + 5,
				order_by: "parent",
			},
		});
	}
};
