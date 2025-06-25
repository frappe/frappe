frappe.provide("frappe.ui");
frappe.provide("frappe.views");
frappe.provide("frappe.web_form_list");

export default class WebFormList {
	constructor(opts) {
		Object.assign(this, opts);
		frappe.web_form_list = this;
		this.wrapper = $(".web-list-table");
		this.make_actions();
		this.make_filters();
	}

	refresh() {
		this.rows = [];
		this.web_list_start = 0;
		this.page_length = 10;

		frappe.run_serially([
			() => this.get_list_view_fields(),
			() => this.get_data(),
			() => this.remove_more(),
			() => this.make_table(),
			() => this.create_more(),
		]);
	}

	remove_more() {
		$(".more").remove();
	}

	make_filters() {
		this.filters = {};
		this.filter_input = [];
		let filter_area = $(".web-list-filters");

		frappe
			.call("frappe.website.doctype.web_form.web_form.get_web_form_filters", {
				web_form_name: this.web_form_name,
			})
			.then((response) => {
				let fields = response.message;
				fields.length && filter_area.removeClass("hide");
				fields.forEach((field) => {
					if (["Text Editor", "Text", "Small Text"].includes(field.fieldtype)) {
						field.fieldtype = "Data";
					}

					if (["Table", "Signature"].includes(field.fieldtype)) {
						return;
					}

					let input = frappe.ui.form.make_control({
						df: {
							fieldtype: field.fieldtype,
							fieldname: field.fieldname,
							options: field.options,
							input_class: "input-xs",
							only_select: true,
							label: __(field.label, null, field.parent),
							onchange: (event) => {
								this.add_filter(field.fieldname, input.value, field.fieldtype);
								this.refresh();
							},
						},
						parent: filter_area,
						render_input: 1,
						only_input: field.fieldtype == "Check" ? false : true,
					});

					$(input.wrapper)
						.addClass("col-md-2")
						.attr("title", __(field.label, null, field.parent))
						.tooltip({
							delay: { show: 600, hide: 100 },
							trigger: "hover",
						});

					input.$input.attr("placeholder", __(field.label, null, field.parent));
					this.filter_input.push(input);
				});
				this.refresh();
			});
	}

	add_filter(field, value, fieldtype) {
		if (!value) {
			delete this.filters[field];
		} else {
			if (["Data", "Currency", "Float", "Int"].includes(fieldtype)) {
				value = ["like", "%" + value + "%"];
			}
			Object.assign(this.filters, Object.fromEntries([[field, value]]));
		}
	}

	get_list_view_fields() {
		if (this.columns) return this.columns;

		if (this.list_columns) {
			this.columns = this.list_columns.map((df) => {
				return {
					label: df.label,
					fieldname: df.fieldname,
					fieldtype: df.fieldtype,
				};
			});
		}
	}

	fetch_data() {
		if (this.condition_json && JSON.parse(this.condition_json)) {
			let filter = frappe.utils.get_filter_from_json(this.condition_json, this.doctype);
			filter = frappe.utils.get_filter_as_json(filter);
			this.filters = Object.assign(this.filters, JSON.parse(filter));
		}

		let args = {
			method: "frappe.www.list.get_list_data",
			args: {
				doctype: this.doctype,
				limit_start: this.web_list_start,
				limit: this.page_length,
				web_form_name: this.web_form_name,
				...this.filters,
			},
		};

		if (this.no_change(args)) {
			// console.log('throttled');
			return Promise.resolve();
		}

		return frappe.call(args);
	}

	no_change(args) {
		// returns true if arguments are same for the last 3 seconds
		// this helps in throttling if called from various sources
		if (this.last_args && JSON.stringify(args) === this.last_args) {
			return true;
		}
		this.last_args = JSON.stringify(args);
		setTimeout(() => {
			this.last_args = null;
		}, 3000);
		return false;
	}

	async get_data() {
		let response = await this.fetch_data();
		if (response) {
			this.data = await response.message;
		}
	}

	more() {
		this.web_list_start += this.page_length;
		this.fetch_data().then((res) => {
			if (res.message.length === 0) {
				frappe.msgprint(__("No more items to display"));
			}
			this.append_rows(res.message);
		});
	}

	make_table() {
		this.table = $(`<table class="table"></table>`);

		this.make_table_head();
		this.make_table_body();
	}

	make_table_head() {
		let $thead = $(`
			<thead>
				<tr>
					<th>
						<input type="checkbox" class="select-all">
					</th>
					<th>${__("Sr")}.</th>
				</tr>
			</thead>
		`);

		this.check_all = $thead.find("input.select-all");
		this.check_all.on("click", (event) => {
			this.toggle_select_all(event.target.checked);
		});

		this.columns.forEach((col) => {
			let $tr = $thead.find("tr");
			let $th = $(`<th>${__(col.label)}</th>`);
			$th.appendTo($tr);
		});

		$thead.appendTo(this.table);
	}

	make_table_body() {
		if (this.data.length) {
			this.wrapper.empty();

			if (this.table) {
				this.table.find("tbody").remove();

				if (this.check_all.length) {
					this.check_all.prop("checked", false);
				}
			}

			this.append_rows(this.data);
			this.table.appendTo(this.wrapper);
		} else {
			if (this.wrapper.find(".no-result").length) return;

			this.wrapper.empty();
			frappe.has_permission(this.doctype, "", "create", () => {
				this.setup_empty_state();
			});
		}
	}

	setup_empty_state() {
		let new_button = `
			<a
				class="btn btn-primary btn-sm btn-new-doc hidden-xs"
				href="${location.pathname.replace("/list", "")}/new">
				${__("Create a new {0}", [__(this.doctype)])}
			</a>
		`;

		let empty_state = $(`
			<div class="no-result text-muted flex justify-center align-center">
				<div class="text-center">
					<svg class="mb-4 icon icon-xl" style="stroke: var(--text-light);">
						<use href="#icon-small-file"></use>
					</svg>
					<p class="small mb-2">${__("No {0} found", [__(this.doctype)])}</p>
					${new_button}
				</div>
			</div>
		`);

		empty_state.appendTo(this.wrapper);
	}

	append_rows(row_data) {
		let $tbody = this.table.find("tbody");

		if (!$tbody.length) {
			$tbody = $(`<tbody></tbody>`);
			$tbody.appendTo(this.table);
		}

		row_data.forEach((data_item) => {
			let $row_element = $(`<tr id="${data_item.name}"></tr>`);

			let row = new frappe.ui.WebFormListRow({
				row: $row_element,
				doc: data_item,
				columns: this.columns,
				serial_number: this.rows.length + 1,
				events: {
					on_edit: () => this.open_form(data_item.name),
					on_select: () => {
						this.toggle_new();
						this.toggle_delete();
					},
				},
			});

			this.rows.push(row);
			$row_element.appendTo($tbody);
		});
	}

	make_actions() {
		const actions = $(".web-list-actions");

		frappe.has_permission(this.doctype, "", "delete", () => {
			this.add_button(actions, "delete-rows", "danger", true, __("Delete"), () =>
				this.delete_rows()
			);
		});
	}

	add_button(wrapper, name, type, hidden, text, action) {
		if ($(`.${name}`).length) return;

		hidden = hidden ? "hide" : "";
		type = type == "danger" ? "danger button-delete" : type;

		let button = $(`
			<button class="${name} btn btn-${type} btn-sm ml-2 ${hidden}">${text}</button>
		`);

		button.on("click", () => action());
		button.appendTo(wrapper);
	}

	create_more() {
		if (this.rows.length >= this.page_length) {
			const footer = $(".web-list-footer");
			this.add_button(footer, "more", "secondary", false, __("Load More"), () =>
				this.more()
			);
		}
	}

	toggle_select_all(checked) {
		this.rows.forEach((row) => row.toggle_select(checked));
	}

	open_form(name) {
		let path = window.location.pathname;
		if (path.includes("/list")) {
			path = path.replace("/list", "");
		}

		window.location.href = path + "/" + name;
	}

	get_selected() {
		return this.rows.filter((row) => row.is_selected());
	}

	toggle_delete() {
		if (!this.settings.allow_delete) return;
		let btn = $(".delete-rows");
		!this.get_selected().length ? btn.addClass("hide") : btn.removeClass("hide");
	}

	toggle_new() {
		if (!this.settings.allow_delete) return;
		let btn = $(".button-new");
		this.get_selected().length ? btn.addClass("hide") : btn.removeClass("hide");
	}

	delete_rows() {
		if (!this.settings.allow_delete) return;
		frappe
			.call({
				type: "POST",
				method: "frappe.website.doctype.web_form.web_form.delete_multiple",
				args: {
					web_form_name: this.web_form_name,
					docnames: this.get_selected().map((row) => row.doc.name),
				},
			})
			.then(() => {
				this.refresh();
				this.toggle_delete();
				this.toggle_new();
			});
	}
}

frappe.ui.WebFormListRow = class WebFormListRow {
	constructor({ row, doc, columns, serial_number, events, options }) {
		Object.assign(this, { row, doc, columns, serial_number, events });
		this.make_row();
	}

	make_row() {
		// Add Checkboxes
		let $cell = $(`<td class="list-col-checkbox"></td>`);

		this.checkbox = $(`<input type="checkbox">`);
		this.checkbox.on("click", (event) => {
			this.toggle_select(event.target.checked);
			event.stopImmediatePropagation();
		});
		this.checkbox.appendTo($cell);
		$cell.appendTo(this.row);

		// Add Serial Number
		let serialNo = $(`<td class="list-col-serial">${__(this.serial_number)}</td>`);
		serialNo.appendTo(this.row);

		this.columns.forEach((field) => {
			let formatter = frappe.form.get_formatter(field.fieldtype);
			let value =
				(this.doc[field.fieldname] &&
					__(
						formatter(this.doc[field.fieldname], field, { only_value: 1 }, this.doc)
					)) ||
				"";
			let cell = $(`<td><p class="ellipsis">${value}</p></td>`);
			if (field.fieldtype === "Text Editor") {
				value = $(value).addClass("ellipsis");
				cell = $("<td></td>").append(value);
			}
			cell.appendTo(this.row);
		});

		this.row.on("click", () => this.events.on_edit());
	}

	toggle_select(checked) {
		this.checkbox.prop("checked", checked);
		this.events.on_select(checked);
	}

	is_selected() {
		return this.checkbox.prop("checked");
	}
};
