frappe.ui.form.on("Web Form", {
	setup: function () {
		frappe.meta.docfield_map["Web Form Field"].fieldtype.formatter = (value) => {
			const prefix = {
				"Page Break": "--red-600",
				"Section Break": "--blue-600",
				"Column Break": "--yellow-600",
			};
			if (prefix[value]) {
				value = `<span class="bold" style="color: var(${prefix[value]})">${value}</span>`;
			}
			return value;
		};

		frappe.meta.docfield_map["Web Form Field"].fieldname.formatter = (value) => {
			if (!value) return;
			return frappe.unscrub(value);
		};

		frappe.meta.docfield_map["Web Form List Column"].fieldname.formatter = (value) => {
			if (!value) return;
			return frappe.unscrub(value);
		};
	},

	refresh: function (frm) {
		add_embed_link(frm);

		if (frm.doc.is_standard && !frappe.boot.developer_mode) {
			frm.disable_form();
			frappe.show_alert(
				__("Standard Web Forms can not be modified, duplicate the Web Form instead.")
			);
		}
		on_controlled_access_change(frm);

		frm.trigger("set_fields");
		frm.trigger("add_get_fields_button");
		frm.trigger("add_publish_button");
		frm.trigger("render_condition_table");
		frm.trigger("render_dynamic_filters_table");
		render_form_builder(frm);
		sync_form_sidebar(frm);
	},

	on_tab_change: function (frm) {
		// the builder is a full-bleed canvas, so the desk chrome steps aside
		const on_builder_tab = frm.get_active_tab()?.df?.fieldname === "form_builder_tab";

		frm.footer?.wrapper.toggle(!on_builder_tab);
		frm.form_wrapper.find(".form-message").toggle(!on_builder_tab);
		frm.form_wrapper.toggleClass("mb-1", on_builder_tab);
		sync_form_sidebar(frm);
	},

	login_required: on_controlled_access_change,

	key_required: on_controlled_access_change,

	anonymous: function (frm) {
		if (frm.doc.anonymous) {
			frm.set_value("login_required", 0);
		}
	},

	validate: function (frm) {
		// must run before the checks below, which read web_form_fields
		flush_form_builder(frm);

		!frm.doc.allow_multiple && frm.set_value("allow_delete", 0);
		frm.doc.allow_multiple && frm.set_value("show_list", 1);

		// a field-less web form is allowed: it renders blank, and always has
		const page_breaks =
			frm.doc.web_form_fields?.filter((f) => f.fieldtype == "Page Break") ?? [];
		validate_page_break_limit(page_breaks.length);
	},

	add_publish_button(frm) {
		frm.add_custom_button(frm.doc.published ? __("Unpublish") : __("Publish"), () => {
			frm.set_value("published", !frm.doc.published);
			frm.save();
		});
	},

	add_get_fields_button(frm) {
		frm.add_custom_button(__("Get Fields"), () => {
			// flush first, or fields only on the canvas show unticked and get added twice
			flush_form_builder(frm);

			get_fields_for_doctype(frm.doc.doc_type).then(
				(fields) => new GetFieldsDialog(frm, fields)
			);
		});
	},

	set_fields(frm) {
		let doc = frm.doc;

		let as_select_option = (df) => ({
			label: df.label,
			value: df.fieldname,
		});
		let update_options = (fields) => {
			frm.fields_dict.web_form_fields.grid.update_docfield_property(
				"fieldname",
				"options",
				fields.map(as_select_option)
			);
			frm.fields_dict.list_columns.grid.update_docfield_property(
				"fieldname",
				"options",
				fields
					.filter(
						(df) =>
							!frappe.model.no_value_type.includes(df.fieldtype) &&
							df.is_virtual !== 1
					)
					.map(as_select_option)
			);
		};

		if (!doc.doc_type) {
			update_options([]);
			frm.set_df_property("amount_field", "options", []);
			return;
		}

		update_options([
			{ label: __("Fetching fields from {0}...", [doc.doc_type]), fieldname: "" },
		]);

		get_fields_for_doctype(doc.doc_type).then((fields) => {
			update_options(fields);

			let currency_fields = fields
				.filter((df) => ["Currency", "Float"].includes(df.fieldtype))
				.map(as_select_option);
			if (!currency_fields.length) {
				currency_fields = [
					{
						label: __("No currency fields in {0}", [doc.doc_type]),
						value: "",
						disabled: true,
					},
				];
			}
			frm.set_df_property("amount_field", "options", currency_fields);
		});
	},

	title: function (frm) {
		if (frm.doc.__islocal) {
			var page_name = frm.doc.title.toLowerCase().replace(/ /g, "-");
			frm.set_value("route", page_name);
		}
	},

	doc_type: function (frm) {
		frm.trigger("set_fields");
		// so the add-field picker offers the new doctype's fields
		render_form_builder(frm);
	},

	allow_multiple: function (frm) {
		frm.doc.allow_multiple && frm.set_value("show_list", 1);
	},

	before_save: function (frm) {
		let dynamic_filters = JSON.parse(frm.doc.dynamic_filters_json || "null");
		let static_filters = JSON.parse(frm.doc.condition_json || "[]");
		static_filters = frappe.dashboard_utils.remove_common_static_filter_values(
			static_filters,
			dynamic_filters
		);
		frm.set_value("condition_json", JSON.stringify(static_filters));
		frm.trigger("render_condition_table");
		frm.trigger("render_dynamic_filters_table");
	},

	render_condition_table: function (frm) {
		let wrapper = $(frm.get_field("condition_json").wrapper).empty();
		let table = $(`
			<style>
			.table-bordered th, .table-bordered td {
				border: none;
				border-right: 1px solid var(--border-color);
			}
			.table-bordered td {
				border-top: 1px solid var(--border-color);
			}
			.table thead th {
				border-bottom: none;
				font-weight: var(--weight-regular);
			}
			tr th:last-child, tr td:last-child{
				border-right: none;
			}
			thead {
				font-size: var(--text-sm);
				color: var(--gray-600);
				background-color: var(--subtle-fg);
			}
			thead th:first-child {
				border-top-left-radius: 9px;
			}
			thead th:last-child {
				border-top-right-radius: 9px;
			}
			</style>

			<table class="table table-bordered" style="cursor:pointer; margin:0px; border-radius: 10px; border-spacing: 0; border-collapse: separate;">
			<thead>
				<tr>
					<th>${__("Filter")}</th>
					<th style="width: 20%">${__("Condition")}</th>
					<th>${__("Value")}</th>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`).appendTo(wrapper);
		$(`<p class="text-muted small mt-2">${__("Click table to edit")}</p>`).appendTo(wrapper);

		let filters = JSON.parse(frm.doc.condition_json || "[]");
		let filters_set = false;

		let fields = [
			{
				fieldtype: "HTML",
				fieldname: "filter_area",
			},
		];

		if (filters?.length) {
			filters.forEach((filter) => {
				const filter_row = $(`<tr>
							<td>${filter[1]}</td>
							<td>${filter[2] || ""}</td>
							<td>${filter[3]}</td>
						</tr>`);

				table.find("tbody").append(filter_row);
			});
			filters_set = true;
		}

		if (!filters_set) {
			const filter_row = $(`<tr><td colspan="3" class="text-muted text-center">
				${__("Click to Set Filters")}</td></tr>`);
			table.find("tbody").append(filter_row);
		}

		table.on("click", () => {
			let dialog = new frappe.ui.Dialog({
				title: __("Set Filters"),
				fields: fields,
				primary_action: function () {
					let values = this.get_values();
					if (values) {
						this.hide();
						let filters = frm.filter_group.get_filters();
						frm.set_value("condition_json", JSON.stringify(filters));
						frm.trigger("render_condition_table");
					}
				},
				primary_action_label: "Set",
			});

			frm.filter_group = new frappe.ui.FilterGroup({
				parent: dialog.get_field("filter_area").$wrapper,
				doctype: frm.doc.doc_type,
				on_change: () => {},
			});
			filters && frm.filter_group.add_filters_to_filter_group(filters);

			dialog.show();

			dialog.set_values(filters);
		});
	},
	render_dynamic_filters_table(frm) {
		let wrapper = $(frm.get_field("dynamic_filters_json").wrapper).empty();

		frm.dynamic_filter_table = $(`<table class="table table-bordered" style="cursor:${
			frm.has_perm("write") ? "pointer" : "default"
		}; margin:0px;">
			<thead>
				<tr>
					<th style="width: 20%">${__("Filter")}</th>
					<th style="width: 20%">${__("Condition")}</th>
					<th>${__("Value")}</th>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`).appendTo(wrapper);

		frm.dynamic_filters =
			frm.doc.dynamic_filters_json && frm.doc.dynamic_filters_json.length > 2
				? JSON.parse(frm.doc.dynamic_filters_json)
				: null;

		frm.trigger("set_dynamic_filters_in_table");

		let filters = JSON.parse(frm.doc.condition_json || "[]");

		let fields = frappe.dashboard_utils.get_fields_for_dynamic_filter_dialog(
			true,
			filters,
			frm.dynamic_filters
		);

		// Override description to show Python expressions (evaluated server-side)
		let desc_field = fields.find((f) => f.fieldname === "description");
		if (desc_field) {
			desc_field.options = `<div>
				<p>${__("Set dynamic filter values as Python expressions.")}</p>
				<p>${__("For example:")}
					<code>frappe.session.user</code> ${__("or")}
					<code>frappe.utils.now()</code>
				</p>
			</div>`;
		}

		frm.dynamic_filter_table.on("click", () => {
			if (!frm.has_perm("write")) {
				return;
			}

			if (!frappe.boot.developer_mode && frm.doc.is_standard) {
				frappe.throw(__("Cannot edit filters for standard Web Forms"));
			}
			let dialog = new frappe.ui.Dialog({
				title: __("Set Dynamic Filters"),
				fields: fields,
				primary_action: () => {
					let values = dialog.get_values();
					dialog.hide();
					let dynamic_filters = [];
					for (let key of Object.keys(values)) {
						let [doctype, fieldname] = key.split(":");
						dynamic_filters.push([doctype, fieldname, "=", values[key]]);
					}
					frm.set_value("dynamic_filters_json", JSON.stringify(dynamic_filters));
					frm.trigger("set_dynamic_filters_in_table");
				},
				primary_action_label: __("Set"),
			});

			dialog.show();
			if (frm.dynamic_filters) {
				let filter_values = {};
				frm.dynamic_filters.forEach((f) => {
					filter_values[f[0] + ":" + f[1]] = f[3];
				});
				dialog.set_values(filter_values);
			}
		});
	},
	set_dynamic_filters_in_table: function (frm) {
		frm.dynamic_filters =
			frm.doc.dynamic_filters_json && frm.doc.dynamic_filters_json.length > 2
				? JSON.parse(frm.doc.dynamic_filters_json)
				: null;

		if (!frm.dynamic_filters) {
			const filter_row = $(`<tr><td colspan="3" class="text-muted text-center">
				${__("Click to Set Dynamic Filters")}</td></tr>`);
			frm.dynamic_filter_table.find("tbody").html(filter_row);
		} else {
			let filter_rows = "";
			frm.dynamic_filters.forEach((filter) => {
				filter_rows += `<tr>
						<td>${filter[1]}</td>
						<td>${filter[2] || ""}</td>
						<td>${filter[3]}</td>
					</tr>`;
			});
			frm.dynamic_filter_table.find("tbody").html(filter_rows);
		}
	},
});

frappe.ui.form.on("Web Form List Column", {
	fieldname: function (frm, doctype, name) {
		let doc = frappe.get_doc(doctype, name);
		let df = frappe.meta.get_docfield(frm.doc.doc_type, doc.fieldname);
		if (!df) return;
		doc.fieldtype = df.fieldtype;
		doc.label = df.label;
		doc.options = df.options;
		frm.refresh_field("list_columns");
	},
});

frappe.ui.form.on("Web Form Field", {
	fieldtype: function (frm, doctype, name) {
		let doc = frappe.get_doc(doctype, name);

		if (doc.fieldtype == "Page Break") {
			validate_page_break_limit(
				frm.doc.web_form_fields.filter((f) => f.fieldtype == "Page Break").length
			);
		}

		if (["Section Break", "Column Break", "Page Break"].includes(doc.fieldtype)) {
			doc.fieldname = "";
			doc.label = "";
			doc.options = "";
			frm.refresh_field("web_form_fields");
		}
	},
	fieldname: function (frm, doctype, name) {
		let doc = frappe.get_doc(doctype, name);
		let df = frappe.meta.get_docfield(frm.doc.doc_type, doc.fieldname);
		if (!df) return;

		doc.label = df.label;
		doc.fieldtype = df.fieldtype;
		doc.options = df.options;
		doc.reqd = df.reqd;
		doc.default = df.default;
		doc.read_only = df.read_only;
		doc.depends_on = df.depends_on;
		doc.placeholder = df.placeholder;
		doc.description = df.description;
		doc.mandatory_depends_on = df.mandatory_depends_on;
		doc.max_length = df.length;
		doc.read_only_depends_on = df.read_only_depends_on;

		frm.refresh_field("web_form_fields");
	},
});

// one list of the doctype's fields (no breaks), rows already on the form pre-ticked:
// Update adds what was ticked and removes what was unticked
class GetFieldsDialog {
	constructor(frm, fields) {
		this.frm = frm;
		const fieldtypes = frappe.meta
			.get_field("Web Form Field", "fieldtype")
			.options.split("\n");
		this.doctype_fields = fields.filter(
			(df) => fieldtypes.includes(get_web_form_fieldtype(df)) && !df.hidden
		);
		this.fields = this.doctype_fields.filter((df) => !is_layout_field(df));
		this.fields_by_name = Object.fromEntries(this.fields.map((df) => [df.fieldname, df]));
		// builder breaks have no fieldname, and older picker breaks do: skip both
		this.existing_rows = (frm.doc.web_form_fields || []).filter(
			(d) => d.fieldname && !is_layout_field(d)
		);
		this.existing_fieldnames = this.existing_rows.map((d) => d.fieldname);
		// stale: a row the picker cannot re-add, so unselecting it here is the only way out
		this.stale_fieldnames = new Set(
			this.existing_fieldnames.filter((fieldname) => !this.fields_by_name[fieldname])
		);

		if (!this.fields.length && !this.existing_rows.length) {
			frappe.msgprint(__("No fields are available from {0}.", [frm.doc.doc_type]));
			return;
		}
		this.make_dialog();
	}

	make_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Get Fields from {0}", [this.frm.doc.doc_type]),
			fields: [
				// a sibling of the MultiCheck, which scrolls and would clip the search focus ring
				{ fieldtype: "HTML", fieldname: "picker_header" },
				{
					fieldname: "fields",
					fieldtype: "MultiCheck",
					columns: 2,
					sort_options: false,
					options: this.get_options(),
				},
			],
			primary_action_label: __("Update"),
			primary_action: () => this.update(),
			on_page_show: () => {
				this.freeze_list_height();
				frappe.utils.setup_search(this.dialog.$body, ".unit-checkbox", ".label-area");
			},
		});
		this.make_header();
		// not in on_page_show: the dialog takes clicks by then, so this would re-tick what
		// Unselect All cleared. Empty forms only, or it re-ticks rows removed on purpose
		!this.existing_rows.length && this.select_mandatory();
		// Dialog takes no wrapper class, so the scroll cap goes on after construction
		const $fields = this.dialog.get_field("fields").$wrapper;
		$fields.addClass("max-h-80 overflow-y-auto");
		// MultiCheck sets padding: 1em inline, which indents the list past the search box
		$fields.find(".checkbox-options").css("padding", 0);
		this.dialog.show();
	}

	make_header() {
		const $header = $(`
			<div class="filters-search">
				<input
					type="text"
					placeholder="${__("Search")}"
					data-element="search"
					class="form-control input-xs"
				>
			</div>
			<div class="flex flex-wrap gap-2 mt-3 mb-3">
				<button class="btn btn-default btn-xs" data-action="select_all">${__("Select All")}</button>
				<button class="btn btn-default btn-xs" data-action="select_mandatory">
					${__("Select Mandatory")}
				</button>
				<button class="btn btn-default btn-xs" data-action="unselect_all">${__("Unselect All")}</button>
			</div>
		`);
		frappe.utils.bind_actions_with_object($header, this);
		this.dialog.get_field("picker_header").$wrapper.html($header);
	}

	// stale rows stay listed, so they can still be unselected
	get_options() {
		const fieldnames = new Set([
			...this.existing_fieldnames,
			...this.fields.map((df) => df.fieldname),
		]);
		return [...fieldnames].map((fieldname) => {
			// undefined for a stale row
			const df = this.fields_by_name[fieldname];
			const is_stale = this.stale_fieldnames.has(fieldname);
			const warning_title = is_stale
				? this.get_stale_warning_title(fieldname)
				: get_condition_warning_title(df);
			return {
				label_class: is_stale ? "text-muted" : "",
				// MultiCheck renders the label as HTML, and a row label is user input
				label: frappe.utils.escape_html(this.get_label(fieldname)),
				value: fieldname,
				checked: this.existing_fieldnames.includes(fieldname),
				description: df?.fieldtype,
				danger: !!df?.reqd,
				warning: !!warning_title,
				warning_title,
			};
		});
	}

	update() {
		const selected = this.dialog.get_value("fields");
		// read before the rows move. The user is taken to this field afterwards
		const [first_added] = this.get_new_fields(selected);

		// taking the whole doctype takes its layout too, but only if that adds something:
		// rebuilding discards the builder's breaks, which have no fieldname to preserve
		const all_ticked = selected.length === this.dialog.get_field("fields").options.length;
		all_ticked && first_added ? this.rebuild_layout(selected) : this.add_and_remove(selected);

		this.frm.refresh_field("web_form_fields");

		// not scroll_to_field: its highlight glow wraps the whole builder tab
		get_builder_tab(this.frm)?.set_active();
		this.dialog.hide();

		// the canvas is rebuilt from the rows, so the new field exists only after the fetch
		refresh_form_builder(this.frm)?.then(() =>
			reveal_in_form_builder(this.frm, first_added?.fieldname)
		);
	}

	// in DocType order: insert_row places each one against the rows already on the form
	get_new_fields(selected) {
		return this.fields.filter(
			(df) =>
				selected.includes(df.fieldname) && !this.existing_fieldnames.includes(df.fieldname)
		);
	}

	add_and_remove(selected) {
		const removed = this.existing_rows.filter((d) => !selected.includes(d.fieldname));

		// clear_doc also renumbers idx, which filtering the array would not
		removed.forEach((d) => frappe.model.clear_doc(d.doctype, d.name));
		this.get_new_fields(selected).forEach((df) => this.insert_row(df, selected));

		// clear_doc does not dirty the form, and refresh_form_builder would reset __unsaved
		removed.length && this.frm.dirty();
	}

	insert_row(df, fieldnames) {
		const at = this.get_insert_index(df);
		this.add_row(df, fieldnames);
		const rows = this.frm.doc.web_form_fields;

		// add_child appended it, so only a row that belongs further up has to move
		if (at < rows.length - 1) {
			rows.splice(at, 0, rows.pop());
			rows.forEach((d, i) => (d.idx = i + 1));
		}
	}

	// a new field sits where the DocType would put it, relative to the fields the form
	// already has; breaks are never consulted, so the form's own layout is left alone
	get_insert_index(df) {
		const rows = this.frm.doc.web_form_fields;
		const position = this.fields.indexOf(df);
		const row_index = (fieldname) => rows.findIndex((d) => d.fieldname === fieldname);

		for (let i = position - 1; i >= 0; i--) {
			const at = row_index(this.fields[i].fieldname);
			if (at !== -1) return at + 1;
		}
		// nothing before it: sit before the nearest one after, so a new opening field stays
		// inside the form's first section
		for (let i = position + 1; i < this.fields.length; i++) {
			const at = row_index(this.fields[i].fieldname);
			if (at !== -1) return at;
		}
		return rows.length;
	}

	rebuild_layout(selected) {
		const ordered = this.get_ordered_rows(selected);

		// add_child creates the table, and with nothing ticked it never ran
		(this.frm.doc.web_form_fields || [])
			.filter((d) => !ordered.includes(d))
			.forEach((d) => frappe.model.clear_doc(d.doctype, d.name));
		this.frm.doc.web_form_fields = ordered;
		ordered.forEach((d, i) => (d.idx = i + 1));
		this.frm.dirty();
	}

	// existing rows are reused, so their edits survive. An empty break is kept anyway:
	// the portal skips the empty page and the save says so
	get_ordered_rows(selected) {
		const rows = this.doctype_fields
			.filter((df) => is_layout_field(df) || selected.includes(df.fieldname))
			.map(
				(df) =>
					this.existing_rows.find((d) => d.fieldname === df.fieldname) ||
					this.add_row(df, selected)
			);
		// stale rows match no doctype field, so they land at the end
		const stale_rows = this.existing_rows.filter(
			(d) => this.stale_fieldnames.has(d.fieldname) && selected.includes(d.fieldname)
		);
		return [...this.drop_empty_leading_pages(rows), ...stale_rows];
	}

	// page 1 is implicit, so a leading Page Break (what a DocType's opening Tab Break
	// becomes) leaves it blank and pushes every field onto page 2
	drop_empty_leading_pages(rows) {
		const first_field = rows.findIndex((d) => !is_layout_field(d));
		// a Page Break past the first field divides the fields around it, so it stays
		const leading = first_field === -1 ? rows.length : first_field;
		return rows.filter((d, i) => i >= leading || d.fieldtype !== "Page Break");
	}

	add_row(df, fieldnames) {
		return this.frm.add_child("web_form_fields", get_web_form_field_values(df, fieldnames));
	}

	// three ways to go stale: no such field, hidden, or a fieldtype a Web Form cannot render
	get_stale_warning_title(fieldname) {
		const docfield = frappe.meta.get_docfield(this.frm.doc.doc_type, fieldname);
		if (!docfield) {
			return __("Not a field in {0}. Unselect to remove it.", [this.frm.doc.doc_type]);
		}
		if (docfield.hidden) {
			return __("Hidden in {0}, so it cannot be added back. Unselect to remove it.", [
				this.frm.doc.doc_type,
			]);
		}
		return __("A Web Form cannot show this {0} field. Unselect to remove it.", [
			__(get_web_form_fieldtype(docfield)),
		]);
	}

	// a DocType often leaves the label blank, while the row may carry a custom one
	get_label(fieldname) {
		const row = this.existing_rows.find((d) => d.fieldname === fieldname);
		const label = row?.label || this.fields_by_name[fieldname]?.label;
		return label ? __(label) : frappe.unscrub(fieldname);
	}

	select_all() {
		this.set_all_checked(true);
	}

	// unlike the exporter, never unticks: an untick deletes that row on Update
	select_mandatory() {
		const checkboxes = this.dialog
			.get_field("fields")
			.options.filter((option) => option.danger)
			.map((option) => option.$checkbox.find(":checkbox").get(0));
		$(checkboxes).prop("checked", true).trigger("change");
	}

	unselect_all() {
		this.set_all_checked(false);
	}

	// MultiCheck listens for "change", so its get_value() stays in sync
	set_all_checked(checked) {
		this.dialog
			.get_field("fields")
			.$wrapper.find(":checkbox")
			.prop("checked", checked)
			.trigger("change");
	}

	// search hides rows, so an unfixed list resizes on every keystroke. Must run after
	// the dialog paints, or the height reads 0
	freeze_list_height() {
		const $wrapper = this.dialog.get_field("fields").$wrapper;
		$wrapper.height($wrapper.height());
	}
}

// shared by Get Fields and the builder's picker. A condition is kept only if `fieldnames`
// has every field it reads
function get_web_form_field_values(df, fieldnames) {
	return {
		fieldname: df.fieldname,
		label: df.label,
		fieldtype: get_web_form_fieldtype(df),
		options: df.options,
		reqd: df.reqd,
		default: df.default,
		read_only: df.read_only,
		precision: df.precision,
		placeholder: df.placeholder,
		max_length: df.length,
		description: df.description,
		...resolve_field_dependencies(df, fieldnames),
	};
}

function validate_page_break_limit(page_break_count) {
	if (page_break_count >= 10) {
		frappe.throw({
			title: __("Too Many Pages"),
			message: __("There can be only 9 Page Break fields in a Web Form"),
		});
	}
}

function get_fields_for_doctype(doctype) {
	return new Promise((resolve) => frappe.model.with_doctype(doctype, resolve)).then(() => {
		return frappe.meta.get_docfields(doctype).filter((df) => {
			return (
				(frappe.model.is_value_type(df.fieldtype) &&
					!["lft", "rgt"].includes(df.fieldname)) ||
				["Table", "Table MultiSelect"].includes(df.fieldtype) ||
				frappe.model.layout_fields.includes(df.fieldtype)
			);
		});
	});
}

function on_controlled_access_change(frm) {
	const has_controlled_access = frm.doc.login_required || frm.doc.key_required;
	if (!has_controlled_access) {
		frm.set_value("allow_multiple", 0);
		frm.set_value("allow_edit", 0);
		frm.set_value("allow_delete", 0);
		frm.set_value("show_list", 0);
	}
	render_list_settings_message(frm);
}

// the builder and the web_form_fields grid edit one child table without watching each
// other, so builder rows reach the grid only here
function flush_form_builder(frm) {
	const builder = get_form_builder(frm);
	if (!builder) return;

	const result = builder.store.update_fields();
	if (typeof result === "string") {
		frappe.throw(result);
	}
}

function refresh_form_builder(frm) {
	return get_form_builder(frm)?.store.fetch();
}

// a new field can land on a page the user is not looking at, so open that page
function reveal_in_form_builder(frm, fieldname) {
	const store = get_form_builder(frm)?.store;
	if (!store || !fieldname) return;

	const found = find_builder_field(store, fieldname);
	if (!found) return;

	store.activate_tab(found.tab);
	// activate_tab selects the page itself; the field just added is the better target
	store.form.selected_field = found.field.df;
	scroll_to_builder_field(fieldname);
}

function find_builder_field(store, fieldname) {
	for (const tab of store.form.layout?.tabs || []) {
		for (const section of tab.sections || []) {
			for (const column of section.columns || []) {
				const field = column.fields?.find((f) => f.df.fieldname === fieldname);
				if (field) return { tab, field };
			}
		}
	}
}

// scoped to the canvas: a Web Form's own fields carry the same fieldnames as the rows it edits
function scroll_to_builder_field(fieldname, attempts = 10) {
	const field = $(`.form-builder-container [data-fieldname="${fieldname}"]`).closest(
		".field"
	)[0];
	// switching pages re-renders the canvas, so the field may not be mounted yet
	if (!field) {
		attempts && setTimeout(() => scroll_to_builder_field(fieldname, attempts - 1), 50);
		return;
	}
	field.scrollIntoView({ behavior: "smooth", block: "center" });
}

// `frm.sidebar` exists only while Form Sidebar is on
function add_embed_link(frm) {
	if (!frm.sidebar) return;

	// add_user_action returns the <a>, not its row
	frm.embed_link?.closest(".user-action-row").remove();

	frm.embed_link = frm.sidebar
		.add_user_action(__("Copy embed code"))
		.attr("href", "#")
		.on("click", () => {
			const url = frappe.urllib.get_full_url(frm.doc.route);
			const code = `<iframe src="${url}" style="border: none; width: 100%; height: inherit;"></iframe>`;
			frappe.utils.copy_to_clipboard(code, __("Embed code copied"));
		});
}

// the canvas is not a Desk field, so frm.disable_form() never reaches it
function is_builder_read_only(frm) {
	return (frm.doc.is_standard && !frappe.boot.developer_mode) || !frm.has_perm("write");
}

function render_form_builder(frm) {
	const builder = frappe.web_form_builder;
	const mounted_here = !!get_form_builder(frm);

	// a mounted builder falls through, so clearing doc_type blanks its field picker
	if (!frm.doc.doc_type && !mounted_here) return;

	if (mounted_here) {
		builder.docname = frm.doc.name;
		builder.doctype = frm.doc.doc_type;
		builder.force_read_only = is_builder_read_only(frm);
		builder.update_store();
		builder.setup_page_actions();
		builder.store.fetch();
		return;
	}

	// meta cached from before the migrate will not have the field
	if (!frm.fields_dict.form_builder) {
		return;
	}

	const wrapper = $(frm.fields_dict["form_builder"].wrapper);

	// mounted against another frm: repoint it, init(true) reuses the Vue app
	if (builder) {
		builder.$wrapper = wrapper;
		builder.frm = frm;
		builder.page = frm.page;
		builder.docname = frm.doc.name;
		builder.doctype = frm.doc.doc_type;
		builder.is_web_form = true;
		builder.force_read_only = is_builder_read_only(frm);
		builder.init(true);
		builder.store.fetch();
		return;
	}

	// `refresh` can fire again before the bundle loads, mounting a second builder
	if (frm._web_form_builder_loading) return;
	frm._web_form_builder_loading = true;

	frappe
		.require("form_builder.bundle.js")
		.then(() => {
			frappe.web_form_builder = new frappe.ui.FormBuilder({
				wrapper: wrapper,
				frm: frm,
				doctype: frm.doc.doc_type,
				customize: false,
				is_web_form: true,
				tab_fieldname: "form_builder_tab",
				get_source_field_values: get_web_form_field_values,
				validate_page_limit: validate_page_break_limit,
				force_read_only: is_builder_read_only(frm),
			});
			frappe.web_form_builder.docname = frm.doc.name;
		})
		.finally(() => (frm._web_form_builder_loading = false));
}

// hidden on the builder tab and on an unsaved doc. Runs on every refresh, since a save shows
// the sidebar again. Use the class, not an inline display, which would survive that refresh
function sync_form_sidebar(frm) {
	if (!frm.page?.sidebar || frm.page.hide_sidebar || !frappe.boot.desk_settings?.form_sidebar) {
		return;
	}

	const on_builder_tab = frm.get_active_tab()?.df?.fieldname === "form_builder_tab";
	frm.page.sidebar.toggleClass("hide-sidebar", on_builder_tab || frm.is_new());
}

// the builder is a singleton, so it can still point at the Web Form the user just left
function get_form_builder(frm) {
	const builder = frappe.web_form_builder;
	return builder?.store && builder.frm === frm ? builder : null;
}

function get_builder_tab(frm) {
	return frm.layout?.tabs?.find((t) => t.df.fieldname === "form_builder_tab");
}

// deduped, since the three keys often hold the same condition
function get_condition_warning_title(df) {
	const conditions = [
		...new Set([df.depends_on, df.mandatory_depends_on, df.read_only_depends_on]),
	].filter(Boolean);
	return conditions.length ? __("Depends on: {0}", [conditions.join(", ")]) : "";
}

function get_web_form_fieldtype(df) {
	return df.fieldtype == "Tab Break" ? "Page Break" : df.fieldtype;
}

function is_layout_field(df) {
	return ["Section Break", "Column Break", "Page Break"].includes(get_web_form_fieldtype(df));
}

// a condition on a field the form does not carry never sees that field's value
function resolve_field_dependencies(df, selected_fieldnames) {
	const result = {};
	for (const key of ["depends_on", "mandatory_depends_on", "read_only_depends_on"]) {
		if (condition_survives(df[key], selected_fieldnames)) {
			result[key] = df[key];
		}
	}
	return result;
}

// fn: runs a Desk form script method, which a portal page does not have
function condition_survives(condition, selected_fieldnames) {
	if (!condition || condition.startsWith("fn:")) return false;
	return get_referenced_fieldnames(condition).every((f) => selected_fieldnames.includes(f));
}

// a bare condition is doc[condition], as in layout.js evaluate_depends_on_value.
// match both doc.x and doc["x"]: a missed reference would let the condition through
function get_referenced_fieldnames(condition) {
	if (!condition.startsWith("eval:")) return [condition];
	const refs = condition.matchAll(/\bdoc(?:\.(\w+)|\[["'](\w+)["']\])/g);
	return [...refs].map((m) => m[1] || m[2]);
}

function render_list_settings_message(frm) {
	// render list setting message
	if (
		frm.fields_dict["list_setting_message"] &&
		!frm.doc.login_required &&
		!frm.doc.key_required
	) {
		const go_to_access_fields = `
			<code class="pointer" title="${__("Go to Access Control section")}">
				${__("Login Required")}
			</code>
			${__("or")}
			<code class="pointer" title="${__("Go to Access Control section")}">
				${__("Key Required")}
			</code>
		`;
		let message = __(
			"Login or a request key is required to see web form list view. Enable {0} to see list settings",
			[go_to_access_fields]
		);
		$(frm.fields_dict["list_setting_message"].wrapper)
			.html($(`<div class="form-message blue">${message}</div>`))
			.find("code")
			.click(() => frm.scroll_to_field("access_control_section"));
	} else {
		$(frm.fields_dict["list_setting_message"].wrapper).empty();
	}
}
