import { defineStore } from "pinia";
import { create_layout, scrub_field_names } from "./utils";
import { computed, nextTick, ref } from "vue";
import { useDebouncedRefHistory, onKeyDown } from "@vueuse/core";

export const useStore = defineStore("form-builder-store", () => {
	let doctype = ref("");
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
	let preview = ref(false);
	let drag = ref(false);
	let get_animation = "cubic-bezier(0.34, 1.56, 0.64, 1)";
	let ref_history = ref(null);

	// Getters
	let get_docfields = computed(() => {
		return is_customize_form.value ? custom_docfields.value : docfields.value;
	});

	let current_tab = computed(() => {
		return form.value.layout.tabs.find((tab) => tab.df.name == form.value.active_tab);
	});

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

	async function fetch() {
		await frappe.model.clear_doc("DocType", doctype.value);
		await frappe.model.with_doctype(doctype.value);

		if (is_customize_form.value) {
			await frappe.model.with_doc("Customize Form");
			let _doc = frappe.get_doc("Customize Form");
			_doc.doc_type = doctype.value;
			let r = await frappe.call({ method: "fetch_to_customize", doc: _doc });
			doc.value = r.docs[0];
		} else {
			doc.value = await frappe.db.get_doc("DocType", doctype.value);
		}

		if (!get_docfields.value.length) {
			let docfield = is_customize_form.value ? "Customize Form Field" : "DocField";
			await frappe.model.with_doctype(docfield);
			let df = frappe.get_meta(docfield).fields;
			if (is_customize_form.value) {
				custom_docfields.value = df;
			} else {
				docfields.value = df;
			}
		}

		form.value.layout = get_layout();
		form.value.active_tab = form.value.layout.tabs[0].df.name;
		form.value.selected_field = null;

		nextTick(() => {
			dirty.value = false;
			read_only.value =
				!is_customize_form.value && !frappe.boot.developer_mode && !doc.value.custom;
			preview.value = false;
		});

		setup_undo_redo();
		setup_breadcrumbs();
	}

	let undo_redo_keyboard_event = onKeyDown(true, (e) => {
		if (!ref_history.value) return;
		if (e.ctrlKey || e.metaKey) {
			if (e.key === "z" && !e.shiftKey && ref_history.value.canUndo) {
				ref_history.value.undo();
			} else if (e.key === "z" && e.shiftKey && ref_history.value.canRedo) {
				ref_history.value.redo();
			}
		}
	});

	function setup_undo_redo() {
		ref_history.value = useDebouncedRefHistory(form, { deep: true, debounce: 100 });

		undo_redo_keyboard_event;
	}

	function setup_breadcrumbs() {
		let breadcrumbs = `
			<li><a href="/app/doctype">${__("DocType")}</a></li>
			<li><a href="/app/doctype/${doctype.value}">${__(doctype.value)}</a></li>
		`;
		if (is_customize_form.value) {
			breadcrumbs = `
				<li><a href="/app/customize-form?doc_type=${doctype.value}">
					${__("Customize Form")}
				</a></li>
			`;
		}
		breadcrumbs += `<li class="disabled"><a href="#">${__("Form Builder")}</a></li>`;
		frappe.breadcrumbs.clear();
		frappe.breadcrumbs.$breadcrumbs.append(breadcrumbs);
	}

	function reset_changes() {
		fetch();
	}

	function validate_fields(fields, is_table) {
		fields = scrub_field_names(fields);

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
				frappe.throw(__("Fieldname {0} appears multiple times", get_field_data(df)));
			}

			// Link & Table fields should always have options set
			if (in_list(["Link", ...frappe.model.table_fields], df.fieldtype) && !df.options) {
				frappe.throw(
					__("Options is required for field {0} of type {1}", get_field_data(df))
				);
			}

			// Do not allow if field is hidden & required but doesn't have default value
			if (df.hidden && df.reqd && !df.default) {
				frappe.throw(
					__(
						"{0} cannot be hidden and mandatory without any default value",
						get_field_data(df)
					)
				);
			}

			// In List View is not allowed for some fieldtypes
			if (df.in_list_view && in_list(not_allowed_in_list_view, df.fieldtype)) {
				frappe.throw(
					__(
						"'In List View' is not allowed for field {0} of type {1}",
						get_field_data(df)
					)
				);
			}

			// In Global Search is not allowed for no_value_type fields
			if (df.in_global_search && in_list(frappe.model.no_value_type, df.fieldtype)) {
				frappe.throw(
					__(
						"'In Global Search' is not allowed for field {0} of type {1}",
						get_field_data(df)
					)
				);
			}
		});
	}

	async function save_changes() {
		if (!dirty.value) {
			frappe.show_alert({ message: __("No changes to save"), indicator: "orange" });
			return;
		}

		frappe.dom.freeze(__("Saving..."));

		try {
			if (is_customize_form.value) {
				let _doc = frappe.get_doc("Customize Form");
				_doc.doc_type = doctype.value;
				_doc.fields = get_updated_fields();
				validate_fields(_doc.fields, _doc.istable);
				await frappe.call({ method: "save_customization", doc: _doc });
			} else {
				doc.value.fields = get_updated_fields();
				validate_fields(doc.value.fields, doc.value.istable);
				await frappe.call("frappe.client.save", { doc: doc.value });
				frappe.toast("Fields Table Updated");
			}
			fetch();
		} catch (e) {
			console.error(e);
		} finally {
			frappe.dom.unfreeze();
		}
	}

	function get_updated_fields() {
		let fields = [];
		let idx = 0;

		let layout_fields = JSON.parse(JSON.stringify(form.value.layout.tabs));

		layout_fields.forEach((tab, i) => {
			if (
				(i == 0 && is_df_updated(tab.df, get_df("Tab Break", "", __("Details")))) ||
				i > 0
			) {
				idx++;
				tab.df.idx = idx;
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
						fields.push(column.df);
					}

					column.fields.forEach((field) => {
						idx++;
						field.df.idx = idx;
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
		delete df.name;
		delete new_df.name;
		return JSON.stringify(df) != JSON.stringify(new_df);
	}

	function get_layout() {
		return create_layout(doc.value.fields);
	}

	return {
		doctype,
		doc,
		form,
		dirty,
		read_only,
		is_customize_form,
		preview,
		drag,
		get_animation,
		get_docfields,
		current_tab,
		selected,
		get_df,
		has_standard_field,
		fetch,
		reset_changes,
		validate_fields,
		save_changes,
		get_updated_fields,
		is_df_updated,
		get_layout,
	};
});
