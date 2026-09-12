import { defineStore } from "pinia";
import {
	create_layout,
	scrub_field_names,
	load_doctype_model,
	section_boilerplate,
} from "./utils";
import { computed, nextTick, ref } from "vue";
import { useDebouncedRefHistory, onKeyDown, useActiveElement } from "@vueuse/core";

export const useStore = defineStore("form-builder-store", () => {
	let doctype = ref("");
	let frm = ref(null);
	let doc = ref(null);
	let docfields = ref([]);
	let custom_docfields = ref([]);
	let form = ref({
		layout: {},
		active_tab: null,
		selected_field: null,
	});
	let dirty = ref(false);
	let read_only = ref(false);
	let is_customize_form = ref(false);
	let is_layout_form = ref(false);
	let is_web_form = ref(false);
	// tab hosting the builder, null for callers that do not set one
	let tab_fieldname = ref(null);
	let source_doctype_fields = ref([]);
	let preview = ref(false);
	let drag = ref(false);
	let get_animation = "cubic-bezier(0.34, 1.56, 0.64, 1)";
	let ref_history = ref(null);

	// Properties that DocType Layout can override per-field
	const LAYOUT_OVERRIDE_PROPS = [
		"label",
		"hidden",
		"reqd",
		"read_only",
		"default",
		"description",
		"depends_on",
		"mandatory_depends_on",
		"read_only_depends_on",
		"bold",
		"allow_in_quick_entry",
		"in_list_view",
		"in_standard_filter",
		"translatable",
	];

	// structural rows name no source field, so they carry no fieldname and no options
	const WEB_FORM_STRUCTURAL_FIELDTYPES = ["Section Break", "Column Break", "Page Break"];

	const WEB_FORM_FIELD_PROPS = [
		"fieldname",
		"label",
		"fieldtype",
		"options",
		"reqd",
		"default",
		"read_only",
		"precision",
		"depends_on",
		"placeholder",
		"max_length",
		"description",
		"mandatory_depends_on",
		"read_only_depends_on",
		// not seeded by Desk, but must round-trip or the builder zeroes them on save
		"hidden",
		"max_value",
		"show_in_filter",
		"allow_read_on_all_link_options",
	];

	// Getters
	let get_docfields = computed(() => {
		return is_customize_form.value ? custom_docfields.value : docfields.value;
	});

	let current_tab = computed(() => {
		return form.value.layout.tabs.find((tab) => tab.df.name == form.value.active_tab);
	});

	const active_element = useActiveElement();
	const not_using_input = computed(
		() =>
			active_element.value?.readOnly ||
			active_element.value?.disabled ||
			(active_element.value?.tagName !== "INPUT" &&
				active_element.value?.tagName !== "TEXTAREA")
	);

	// Actions
	function selected(name) {
		return form.value.selected_field?.name == name;
	}

	function get_df(fieldtype, fieldname = "", label = "") {
		let docfield = is_customize_form.value ? "Customize Form Field" : "DocField";
		let df = frappe.model.get_new_doc(docfield);
		df.name = frappe.utils.get_random(8);
		df.fieldtype = fieldtype;
		df.fieldname = fieldname;
		df.label = label;
		is_customize_form.value && (df.is_custom_field = 1);
		return df;
	}

	function has_standard_field(field) {
		if (!is_customize_form.value) return;
		if (!field.df.is_custom_field) return true;

		let children = {
			"Tab Break": "sections",
			"Section Break": "columns",
			"Column Break": "fields",
		}[field.df.fieldtype];

		if (!children) return false;

		return field[children].some((child) => {
			if (!child.df.is_custom_field) return true;
			return has_standard_field(child);
		});
	}

	function is_user_generated_field(field) {
		return cint(field.df.is_custom_field && !field.df.is_system_generated);
	}

	// by index, not name, since tab names can change after save
	function get_active_tab_index() {
		if (!form.value.layout?.tabs || !form.value.active_tab) return null;
		return form.value.layout.tabs.findIndex((tab) => tab.df.name === form.value.active_tab);
	}

	// restore the previously active tab by index if it still exists
	function restore_active_tab(previous_index) {
		let tabs = form.value.layout.tabs;
		if (previous_index !== null && previous_index >= 0 && previous_index < tabs.length) {
			form.value.active_tab = tabs[previous_index].df.name;
		} else if (tabs.length > 0) {
			form.value.active_tab = tabs[0].df.name;
		} else {
			form.value.active_tab = null;
		}
	}

	// deferred to nextTick so it lands after FormBuilder.vue's layout watcher sets dirty
	function finish_fetch() {
		// Capture dirty state before nextTick so a concurrent frm.dirty() call
		// (e.g. from sync_fields) is not erased by the post-fetch cleanup.
		const was_frm_dirty = !!frm.value.doc.__unsaved;
		nextTick(() => {
			dirty.value = false;
			if (!was_frm_dirty) {
				frm.value.doc.__unsaved = 0;
				// redraw rather than clear, or the doc's own status (Published) goes too
				frm.value.toolbar.set_indicator();
			}
			read_only.value = false;
			preview.value = false;
		});
	}

	async function fetch_for_layout() {
		// Populate DocField meta for the properties panel
		if (!frappe.get_meta("DocField")) {
			await load_doctype_model("DocField");
		}
		docfields.value = frappe.get_meta("DocField").fields;

		// Load source DocType meta
		let source_dt = doctype.value;
		if (!frappe.get_meta(source_dt)) {
			await load_doctype_model(source_dt);
		}
		source_doctype_fields.value = frappe.get_meta(source_dt).fields;

		// Build merged field list: layout row order + overrides merged onto source field defs
		let layout_rows = frm.value.doc.fields || [];
		let merged_fields;
		if (layout_rows.length > 0) {
			merged_fields = layout_rows
				.map((row) => {
					let sf = source_doctype_fields.value.find(
						(f) => f.fieldname === row.fieldname
					);
					if (!sf) return null;
					let copy = JSON.parse(JSON.stringify(sf));
					for (let prop of LAYOUT_OVERRIDE_PROPS) {
						let val = row[prop];
						if (val !== undefined && val !== null && val !== "") {
							copy[prop] = val;
						}
					}
					return copy;
				})
				.filter(Boolean);
		} else {
			merged_fields = JSON.parse(JSON.stringify(source_doctype_fields.value));
		}

		let previous_active_tab_index = get_active_tab_index();

		doc.value = { fields: merged_fields, custom: 1, istable: 0 };
		form.value.layout = get_layout();

		restore_active_tab(previous_active_tab_index);
		form.value.selected_field = null;

		finish_fetch();

		setup_undo_redo();
	}

	async function fetch_for_web_form() {
		await load_web_form_meta();

		let merged_fields = web_form_rows_to_fields();
		let previous_active_tab_index = get_active_tab_index();

		doc.value = { fields: merged_fields, custom: 1, istable: 0 };
		form.value.layout = get_layout();
		setup_web_form_pages();

		restore_active_tab(previous_active_tab_index);
		form.value.selected_field = null;

		finish_fetch();

		setup_undo_redo();
	}

	async function load_web_form_meta() {
		if (!frappe.get_meta("Web Form Field")) {
			await load_doctype_model("Web Form Field");
		}
		docfields.value = frappe.get_meta("Web Form Field").fields;

		// not for the properties panel — get_df() builds layout nodes from DocField meta
		if (!frappe.get_meta("DocField")) {
			await load_doctype_model("DocField");
		}

		// not used to build the layout, only so the picker can offer unplaced fields
		let source_dt = frm.value.doc.doc_type;
		if (source_dt && !frappe.get_meta(source_dt)) {
			await load_doctype_model(source_dt);
		}
		// same predicate as get_fields_for_doctype() in web_form.js, which feeds the grid
		source_doctype_fields.value = source_dt
			? frappe.get_meta(source_dt).fields.filter(
					(df) =>
						(frappe.model.is_value_type(df.fieldtype) &&
							!["lft", "rgt"].includes(df.fieldname)) ||
						// capital S: "Table Multiselect" matches no field
						["Table", "Table MultiSelect"].includes(df.fieldtype) ||
						frappe.model.layout_fields.includes(df.fieldtype)
			  )
			: [];
	}

	// read direction: web_form_fields rows to layout nodes
	function web_form_rows_to_fields() {
		// a row added from the grid has no fieldtype yet, so it has no layout node
		let rows = (frm.value.doc.web_form_fields || []).filter((row) => row.fieldtype);

		let fields = rows.map((row) => {
			let df = get_df(row.fieldtype, row.fieldname, row.label);

			for (let prop of WEB_FORM_FIELD_PROPS) {
				if (row[prop] !== undefined) {
					df[prop] = row[prop];
				}
			}

			// a Page Break in a Web Form is a tab boundary
			if (df.fieldtype === "Page Break") {
				df.fieldtype = "Tab Break";
			}

			return df;
		});

		// page 1 is implicit — N pages are stored as N-1 Page Break rows, so prepend its tab
		fields.unshift(get_df("Tab Break"));

		return fields;
	}

	function setup_web_form_pages() {
		// mark page 1 as the tab with no backing row, the way create_layout() does
		form.value.layout.tabs[0].is_first = true;

		form.value.layout.tabs.forEach((tab, i) => {
			// a Page Break row carries no label, so number the pages by position
			tab.df.label = __("Page {0}", [i + 1]);

			// create_layout() prunes empty sections, leaving a page with no drop target
			if (!tab.sections.length) tab.sections.push(section_boilerplate());
		});
	}

	async function fetch() {
		if (is_layout_form.value) return fetch_for_layout();
		if (is_web_form.value) return fetch_for_web_form();

		doc.value = frm.value.doc;
		if (doctype.value.startsWith("new-doctype-") && !doc.value.fields?.length) {
			frappe.model.with_doctype("DocType").then(() => {
				frappe.listview_settings["DocType"].new_doctype_dialog();
			});
			// redirect to /doctype
			frappe.set_route("List", "DocType");
			return;
		}

		if (!get_docfields.value.length) {
			let docfield = is_customize_form.value ? "Customize Form Field" : "DocField";
			if (!frappe.get_meta(docfield)) {
				await load_doctype_model(docfield);
			}
			let df = frappe.get_meta(docfield).fields;
			if (is_customize_form.value) {
				custom_docfields.value = df;
			} else {
				docfields.value = df;
			}
		}

		let previous_active_tab_index = get_active_tab_index();

		form.value.layout = get_layout();

		restore_active_tab(previous_active_tab_index);

		form.value.selected_field = null;

		nextTick(() => {
			if (!doctype.value.startsWith("new-doctype-")) {
				dirty.value = false;
				frm.value.doc.__unsaved = 0;
				frm.value.page.clear_indicator();
			}
			read_only.value =
				!is_customize_form.value && !frappe.boot.developer_mode && !doc.value.custom;
			preview.value = false;
		});

		setup_undo_redo();
	}

	function is_on_builder_tab() {
		let active_tab = frm.value?.get_active_tab();

		if (!active_tab) return false;

		if (tab_fieldname.value) return active_tab.df.fieldname === tab_fieldname.value;

		return active_tab.label == "Form";
	}

	let undo_redo_keyboard_event = onKeyDown(true, (e) => {
		if (!ref_history.value) return;
		if (is_on_builder_tab() && (e.ctrlKey || e.metaKey)) {
			if (e.key === "z" && !e.shiftKey && ref_history.value.canUndo) {
				ref_history.value.undo();
			} else if (e.key === "z" && e.shiftKey && ref_history.value.canRedo) {
				ref_history.value.redo();
			}
		}
	});

	function setup_undo_redo() {
		// every fetch() lands here; replacing the handle does not stop the old deep watcher
		ref_history.value?.dispose();
		ref_history.value = useDebouncedRefHistory(form, {
			deep: true,
			debounce: 100,
			capacity: 50,
		});

		undo_redo_keyboard_event;
	}

	function validate_fields(fields, is_table) {
		fields = scrub_field_names(fields);
		let error_message = "";

		let has_fields = fields.some((df) => {
			return !["Section Break", "Tab Break", "Column Break"].includes(df.fieldtype);
		});

		if (!has_fields) {
			error_message = __("DocType must have atleast one field");
		}

		let not_allowed_in_list_view = ["Attach Image", ...frappe.model.no_value_type];
		if (is_table) {
			not_allowed_in_list_view = not_allowed_in_list_view.filter((f) => f != "Button");
		}

		function get_field_data(df) {
			let fieldname = `<b>${df.label} (${df.fieldname})</b>`;
			if (!df.label) {
				fieldname = `<b>${df.fieldname}</b>`;
			}
			let fieldtype = `<b>${df.fieldtype}</b>`;
			return [fieldname, fieldtype];
		}

		fields.forEach((df) => {
			// check if fieldname already exist
			let duplicate = fields.filter((f) => f.fieldname == df.fieldname);
			if (duplicate.length > 1) {
				error_message = __("Fieldname {0} appears multiple times", get_field_data(df));
			}

			// Link & Table fields should always have options set
			if (["Link", ...frappe.model.table_fields].includes(df.fieldtype) && !df.options) {
				error_message = __(
					"Options is required for field {0} of type {1}",
					get_field_data(df)
				);
			}

			// Do not allow if field is hidden & required but doesn't have default value
			if (df.hidden && df.reqd && !df.default) {
				error_message = __(
					"{0} cannot be hidden and mandatory without any default value",
					get_field_data(df)
				);
			}

			// In List View is not allowed for some fieldtypes
			if (df.in_list_view && not_allowed_in_list_view.includes(df.fieldtype)) {
				error_message = __(
					"'In List View' is not allowed for field {0} of type {1}",
					get_field_data(df)
				);
			}

			// In Global Search is not allowed for no_value_type fields
			if (df.in_global_search && frappe.model.no_value_type.includes(df.fieldtype)) {
				error_message = __(
					"'In Global Search' is not allowed for field {0} of type {1}",
					get_field_data(df)
				);
			}

			if (df.link_filters === "") {
				delete df.link_filters;
			}

			// check if link_filters format is correct or not
			if (df.link_filters) {
				try {
					let link_filters = JSON.parse(df.link_filters);
				} catch (e) {
					error_message = __(
						"Invalid Filter Format for field {0} of type {1}. Try using filter icon on the field to set it correctly",
						get_field_data(df)
					);
				}
			}
		});

		return error_message;
	}

	// callers throw on a string return — returning undefined would save the old fields
	function write_back_error(e) {
		console.error(e);
		return __(
			"Form Builder could not apply the layout: {0}. The save was cancelled, so your changes are not lost. See the browser console for details.",
			[frappe.utils.escape_html(e.message || e)]
		);
	}

	function update_layout_fields() {
		if (!dirty.value && !frm.value.is_new()) return;

		frappe.dom.freeze(__("Saving..."));

		try {
			let form_builder_fields = get_updated_fields();
			// Convert to DocType Layout Field rows (fieldname + overrideable props only)
			let layout_rows = form_builder_fields
				.map((field) => {
					if (!field.fieldname) return null;
					let row = { fieldname: field.fieldname };
					for (let prop of LAYOUT_OVERRIDE_PROPS) {
						row[prop] = field[prop] !== undefined ? field[prop] : null;
					}
					return row;
				})
				.filter(Boolean);

			frm.value.set_value("fields", layout_rows);
			return layout_rows;
		} catch (e) {
			return write_back_error(e);
		} finally {
			frappe.dom.unfreeze();
		}
	}

	function update_web_form_fields() {
		// no `|| frm.is_new()` here — the grid also writes web_form_fields, so a clean
		// builder must not overwrite rows "Get Fields" added behind its back
		if (!dirty.value) return;

		frappe.dom.freeze(__("Saving..."));

		try {
			let rows = web_form_fields_to_rows(get_updated_fields());
			frm.value.set_value("web_form_fields", rows);
			return rows;
		} catch (e) {
			return write_back_error(e);
		} finally {
			frappe.dom.unfreeze();
		}
	}

	// write direction: layout nodes back to web_form_fields rows
	function web_form_fields_to_rows(fields) {
		// page 1 is implicit, so drop tab 0 — but only if get_updated_fields() kept it,
		// or we would eat page 2's break instead
		let tab_count = fields.filter((df) => df.fieldtype === "Tab Break").length;
		let rows = tab_count === form.value.layout.tabs.length ? fields.slice(1) : fields;

		return rows.map((df, i) => {
			let row = { idx: i + 1 };
			for (let prop of WEB_FORM_FIELD_PROPS) {
				row[prop] = df[prop] !== undefined ? df[prop] : null;
			}
			// a tab boundary is a Page Break in a Web Form
			if (row.fieldtype === "Tab Break") {
				row.fieldtype = "Page Break";
			}

			if (WEB_FORM_STRUCTURAL_FIELDTYPES.includes(row.fieldtype)) {
				row.fieldname = "";
				row.options = "";
			}

			// pages are named by position on read, so the label is never stored
			if (row.fieldtype === "Page Break") {
				row.label = "";
			}

			return row;
		});
	}

	function update_fields() {
		if (is_layout_form.value) {
			return update_layout_fields();
		}

		if (is_web_form.value) {
			return update_web_form_fields();
		}

		if (!dirty.value && !frm.value.is_new()) return;

		frappe.dom.freeze(__("Saving..."));

		try {
			let fields = get_updated_fields();
			let has_error = validate_fields(fields, doc.value.istable);
			if (has_error) return has_error;
			frm.value.set_value("fields", fields);
			return fields;
		} catch (e) {
			return write_back_error(e);
		} finally {
			frappe.dom.unfreeze();
		}
	}

	function get_updated_fields() {
		let fields = [];
		let idx = 0;
		let new_field_name = is_customize_form.value
			? "new-customize-form-field-"
			: "new-docfield-";

		let layout_fields = JSON.parse(JSON.stringify(form.value.layout.tabs));

		layout_fields.forEach((tab, i) => {
			if (
				(i == 0 && is_df_updated(tab.df, get_df("Tab Break", "", __("Details")))) ||
				i > 0
			) {
				idx++;
				tab.df.idx = idx;
				if (tab.df.__unsaved && tab.df.__islocal) {
					tab.df.name = new_field_name + idx;
				}
				fields.push(tab.df);
			}

			tab.sections.forEach((section, j) => {
				// data before section is added
				let fields_copy = JSON.parse(JSON.stringify(fields));
				let old_idx = idx;
				section.has_fields = false;

				// do not consider first section if label is not set
				if ((j == 0 && is_df_updated(section.df, get_df("Section Break"))) || j > 0) {
					idx++;
					section.df.idx = idx;
					if (section.df.__unsaved && section.df.__islocal) {
						section.df.name = new_field_name + idx;
					}
					fields.push(section.df);
				}

				section.columns.forEach((column, k) => {
					// do not consider first column if label is not set
					if (
						(k == 0 && is_df_updated(column.df, get_df("Column Break"))) ||
						k > 0 ||
						column.fields.length == 0
					) {
						idx++;
						column.df.idx = idx;
						if (column.df.__unsaved && column.df.__islocal) {
							column.df.name = new_field_name + idx;
						}
						fields.push(column.df);
					}

					column.fields.forEach((field) => {
						idx++;
						field.df.idx = idx;
						if (field.df.__unsaved && field.df.__islocal) {
							field.df.name = new_field_name + idx;
						}
						fields.push(field.df);
						section.has_fields = true;
					});
				});

				// restore data back to data before section is added.
				if (!section.has_fields) {
					fields = fields_copy || [];
					idx = old_idx;
				}
			});
		});

		return fields;
	}

	function is_df_updated(df, new_df) {
		let df_copy = JSON.parse(JSON.stringify(df));
		let new_df_copy = JSON.parse(JSON.stringify(new_df));
		delete df_copy.name;
		delete new_df_copy.name;
		return JSON.stringify(df_copy) != JSON.stringify(new_df_copy);
	}

	function get_layout() {
		return create_layout(doc.value.fields);
	}

	// Tab actions
	function add_new_tab() {
		// page 1 is implicit, so 10 tabs is the 9 Page Breaks web_form.js validate() allows
		if (is_web_form.value && form.value.layout.tabs.length >= 10) {
			frappe.throw(__("There can be only 9 Page Break fields in a Web Form"));
		}

		// match the numbering fetch_for_web_form() applies on the next read
		let position = form.value.layout.tabs.length + 1;
		let label = is_web_form.value ? __("Page {0}", [position]) : "Tab " + position;

		let tab = {
			df: get_df("Tab Break", "", label),
			sections: [section_boilerplate()],
		};

		form.value.layout.tabs.push(tab);
		activate_tab(tab);
	}

	function activate_tab(tab) {
		form.value.active_tab = tab.df.name;
		form.value.selected_field = tab.df;

		// scroll to active tab
		nextTick(() => {
			$(".tabs .tab.active")[0]?.scrollIntoView({
				behavior: "smooth",
				inline: "center",
				block: "nearest",
			});
		});
	}

	return {
		doctype,
		frm,
		doc,
		form,
		dirty,
		read_only,
		is_customize_form,
		is_layout_form,
		is_web_form,
		tab_fieldname,
		source_doctype_fields,
		preview,
		drag,
		get_animation,
		get_docfields,
		current_tab,
		not_using_input,
		selected,
		get_df,
		has_standard_field,
		is_user_generated_field,
		fetch,
		validate_fields,
		update_fields,
		get_updated_fields,
		is_df_updated,
		get_layout,
		add_new_tab,
		activate_tab,
	};
});
