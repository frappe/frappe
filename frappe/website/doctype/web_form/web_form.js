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
		frm.embed_link && frm.embed_link.remove();

		// get iframe url for web form
		frm.embed_link = frm.sidebar
			.add_user_action(__("Copy embed code"))
			.attr("href", "#")
			.on("click", () => {
				const url = frappe.urllib.get_full_url(frm.doc.route);
				const code = `<iframe src="${url}" style="border: none; width: 100%; height: inherit;"></iframe>`;
				frappe.utils.copy_to_clipboard(code, __("Embed code copied"));
			});

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
	},

	on_tab_change: function (frm) {
		// the builder is a full-bleed canvas, so the desk chrome steps aside
		const on_builder_tab = frm.get_active_tab()?.df?.fieldname === "form_builder_tab";

		frm.footer?.wrapper.toggle(!on_builder_tab);
		frm.form_wrapper.find(".form-message").toggle(!on_builder_tab);
		frm.form_wrapper.toggleClass("mb-1", on_builder_tab);
		toggle_form_sidebar(frm, !on_builder_tab);
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

		if (!frm.doc.web_form_fields?.length) {
			// check_mandatory reports the missing doc_type after this hook
			if (!frm.doc.doc_type) return;

			frm.layout?.tabs?.find((t) => t.df.fieldname === "form_builder_tab")?.set_active();
			frappe.throw(__("Add at least one field to the Web Form"));
		}

		let page_break_count = frm.doc.web_form_fields.filter(
			(f) => f.fieldtype == "Page Break"
		).length;

		if (page_break_count >= 10) {
			frappe.throw(__("There can be only 9 Page Break fields in a Web Form"));
		}
	},

	add_publish_button(frm) {
		frm.add_custom_button(frm.doc.published ? __("Unpublish") : __("Publish"), () => {
			frm.set_value("published", !frm.doc.published);
			frm.save();
		});
	},

	add_get_fields_button(frm) {
		frm.add_custom_button(__("Get Fields"), () => {
			let webform_fieldtypes = frappe.meta
				.get_field("Web Form Field", "fieldtype")
				.options.split("\n");

			// flush first, or fields only on the canvas get offered and appended twice
			flush_form_builder(frm);

			let added_fields = (frm.doc.web_form_fields || []).map((d) => d.fieldname);

			get_fields_for_doctype(frm.doc.doc_type).then((fields) => {
				for (let df of fields) {
					let fieldtype = df.fieldtype;
					if (fieldtype == "Tab Break") {
						fieldtype = "Page Break";
					}
					if (
						webform_fieldtypes.includes(fieldtype) &&
						!added_fields.includes(df.fieldname) &&
						!df.hidden
					) {
						frm.add_child("web_form_fields", {
							fieldname: df.fieldname,
							label: df.label,
							fieldtype: fieldtype,
							options: df.options,
							reqd: df.reqd,
							default: df.default,
							read_only: df.read_only,
							precision: df.precision,
							depends_on: df.depends_on,
							placeholder: df.placeholder,
							max_length: df.length,
							description: df.description,
							mandatory_depends_on: df.mandatory_depends_on,
							read_only_depends_on: df.read_only_depends_on,
						});
					}
				}
				frm.refresh_field("web_form_fields");
				frm.scroll_to_field("web_form_fields");

				// read the new rows back — no grid edit reaches the builder on its own
				refresh_form_builder(frm);
			});
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

	after_save: function (frm) {
		refresh_form_builder(frm);
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
			let page_break_count = frm.doc.web_form_fields.filter(
				(f) => f.fieldtype == "Page Break"
			).length;
			page_break_count >= 10 &&
				frappe.throw(__("There can be only 9 Page Break fields in a Web Form"));
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
	get_form_builder(frm)?.store.fetch();
}

function render_form_builder(frm) {
	const builder = frappe.web_form_builder;
	const mounted_here = !!get_form_builder(frm);

	// a mounted builder falls through, so clearing doc_type blanks its field picker
	if (!frm.doc.doc_type && !mounted_here) return;

	// not init(true) here: it re-runs watch_changes() and stacks a duplicate watchEffect
	if (mounted_here) {
		builder.docname = frm.doc.name;
		builder.doctype = frm.doc.doc_type;
		builder.update_store();
		builder.setup_page_actions();
		builder.store.fetch();
		return;
	}

	// meta cached from before the migrate will not have the field
	if (!frm.fields_dict.form_builder) {
		console.warn("Web Form: form_builder field missing, skipping builder mount.");
		return;
	}

	const wrapper = $(frm.fields_dict["form_builder"].wrapper).closest(".tab-pane");

	// mounted against another frm: repoint it, init(true) reuses the Vue app
	if (builder) {
		builder.$wrapper = wrapper;
		builder.frm = frm;
		builder.page = frm.page;
		builder.docname = frm.doc.name;
		builder.doctype = frm.doc.doc_type;
		builder.is_web_form = true;
		builder.init(true);
		keep_builder_tab_visible(frm);
		builder.store.fetch();
		return;
	}

	// `refresh` can fire again before the bundle loads, mounting a second builder
	if (frm._web_form_builder_loading) return;
	frm._web_form_builder_loading = true;

	frappe.require("form_builder.bundle.js").then(() => {
		frappe.web_form_builder = new frappe.ui.FormBuilder({
			wrapper: wrapper,
			frm: frm,
			doctype: frm.doc.doc_type,
			customize: false,
			is_web_form: true,
			tab_fieldname: "form_builder_tab",
		});
		frappe.web_form_builder.docname = frm.doc.name;
		frm._web_form_builder_loading = false;

		keep_builder_tab_visible(frm);
	});
}

// refresh_tabs() hides tabs whose sections scan as empty, which this one always does, and
// it re-runs on every layout.refresh(), so a one-off toggle does not hold
function keep_builder_tab_visible(frm) {
	const builder_tab = frm.layout?.tabs?.find((t) => t.df.fieldname === "form_builder_tab");
	if (!builder_tab) return;

	if (!builder_tab._web_form_builder_patched) {
		builder_tab._web_form_builder_patched = true;
		const _orig_tab_refresh = builder_tab.refresh.bind(builder_tab);
		builder_tab.refresh = function () {
			_orig_tab_refresh();
			if (frappe.web_form_builder) this.toggle(true);
		};
	}

	builder_tab.toggle(true);
}

// page.scss pins the main column width for every Form route, so hiding the sidebar has to
// clear the inline widths too
function toggle_form_sidebar(frm, show) {
	if (!frm.page?.sidebar || frm.page.hide_sidebar || !frappe.boot.desk_settings?.form_sidebar) {
		return;
	}

	frm.page.sidebar.toggle(show);
	frm.page.wrapper.find(".layout-main-section-wrapper").css({
		width: show ? "" : "100%",
		flex: show ? "" : "1 0 100%",
	});
}

// the builder is a singleton, so it can still point at the Web Form the user just left
function get_form_builder(frm) {
	const builder = frappe.web_form_builder;
	return builder?.store && builder.frm === frm ? builder : null;
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
