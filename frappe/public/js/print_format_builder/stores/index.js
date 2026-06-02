import { create_default_layout, pluck } from "../utils";
import { watch, ref, inject, computed, nextTick } from "vue";

export function getStore(print_format_name) {
	// variables
	let letterhead_name = ref(null);
	let print_format = ref(null);
	let letterhead = ref(null);
	let doctype = ref(null);
	let meta = ref(null);
	let layout = ref(null);
	let dirty = ref(false);
	let edit_letterhead = ref(false);
	let scroll_to_section = ref(null);
	let selected_field = ref(null);
	let selected_section = ref(null);
	let selected_letterhead = ref(false);
	let selected_lh_footer = ref(false);
	let preview_doc = ref(null);
	let preview_doc_name = ref(null);

	// methods
	function fetch() {
		return new Promise((resolve) => {
			frappe.model.clear_doc("Print Format", print_format_name);
			frappe.model.with_doc("Print Format", print_format_name, () => {
				let _print_format = frappe.get_doc("Print Format", print_format_name);
				frappe.model.with_doctype(_print_format.doc_type, () => {
					meta.value = frappe.get_meta(_print_format.doc_type);
					print_format.value = _print_format;
					layout.value = get_layout() || get_default_layout();
					// Migrate legacy string header/footer to section objects
					layout.value.header = migrate_to_section(layout.value.header);
					layout.value.footer = migrate_to_section(layout.value.footer);
					edit_letterhead.value = false;
					selected_field.value = null;
					selected_section.value = null;
					selected_letterhead.value = false;
					selected_lh_footer.value = false;

					// load the letter head stored in format_data, if any
					const lh_name = layout.value?.letter_head;
					const load_lh = lh_name
						? frappe.db
								.get_doc("Letter Head", lh_name)
								.then((doc) => (letterhead.value = doc))
						: Promise.resolve((letterhead.value = null));

					load_lh.then(() => {
						nextTick(() => (dirty.value = false));
						resolve();
					});
				});
			});
		});
	}
	function migrate_to_section(value) {
		if (value && typeof value === "object" && value.columns) return value;
		const old_html = typeof value === "string" && value.trim() ? value : null;
		return {
			columns: [
				{
					label: "",
					fields: old_html
						? [
								{
									fieldtype: "HTML",
									fieldname: "_zone_html",
									label: "",
									html: old_html,
								},
						  ]
						: [],
				},
			],
		};
	}
	function update({ fieldname, value }) {
		print_format.value[fieldname] = value;
	}
	function save_changes() {
		frappe.dom.freeze(__("Saving..."));

		layout.value.sections = layout.value.sections
			.filter((section) => !section.remove)
			.map((section) => {
				section.columns = section.columns.map((column) => {
					column.fields = column.fields
						.filter((df) => !df.remove)
						.map((df) => {
							if (df.table_columns) {
								df.table_columns = df.table_columns.map((tf) => {
									return pluck(tf, [
										"label",
										"fieldname",
										"fieldtype",
										"options",
										"width",
										"field_template",
									]);
								});
							}
							return pluck(df, [
								"label",
								"fieldname",
								"fieldtype",
								"options",
								"table_columns",
								"table_style",
								"table_bordered",
								"table_header",
								"html",
								"field_template",
								"show_label",
								"align",
							]);
						});
					return column;
				});
				return section;
			});

		// Clean up header/footer section fields
		const zone_pluck_keys = [
			"label",
			"fieldname",
			"fieldtype",
			"options",
			"table_columns",
			"table_style",
			"table_bordered",
			"table_header",
			"html",
			"field_template",
			"show_label",
			"align",
		];
		function clean_zone(zone) {
			if (!zone || !zone.columns) return zone;
			zone.columns = zone.columns.map((column) => {
				column.fields = column.fields
					.filter((df) => !df.remove)
					.map((df) => pluck(df, zone_pluck_keys));
				return column;
			});
			return zone;
		}
		layout.value.header = clean_zone(layout.value.header);
		layout.value.footer = clean_zone(layout.value.footer);

		print_format.value.format_data = JSON.stringify(layout.value);

		frappe
			.call("frappe.client.save", {
				doc: print_format.value,
			})
			.then(() => {
				if (letterhead.value && letterhead.value._dirty) {
					return frappe
						.call("frappe.client.save", {
							doc: letterhead.value,
						})
						.then((r) => (letterhead.value = r.message));
				}
			})
			.then(() => fetch())
			.then(() => {
				frappe.show_alert({ message: __("Saved"), indicator: "green" });
			})
			.always(() => {
				frappe.dom.unfreeze();
			});
	}
	function reset_changes() {
		fetch();
	}
	function load_preview_doc(name) {
		if (!name) {
			preview_doc.value = null;
			preview_doc_name.value = null;
			return;
		}
		preview_doc_name.value = name;
		frappe.db.get_doc(print_format.value.doc_type, name).then((doc) => {
			preview_doc.value = doc;
		});
	}
	function get_layout() {
		if (print_format.value && print_format.value.format_data) {
			if (typeof print_format.value.format_data == "string") {
				try {
					return JSON.parse(print_format.value.format_data);
				} catch {
					return null;
				}
			}
			return print_format.value.format_data;
		}
		return null;
	}
	function get_default_layout() {
		return create_default_layout(meta.value, print_format.value);
	}
	function change_letterhead(_letterhead) {
		return frappe.db.get_doc("Letter Head", _letterhead).then((doc) => {
			letterhead.value = doc;
			// persist the letter head name inside format_data (layout) so it
			// survives save → reload without needing a separate doctype field
			if (layout.value) {
				layout.value.letter_head = _letterhead;
			}
		});
	}

	// watch
	watch(layout, () => {
		dirty.value = true;
	});
	watch(print_format, () => {
		dirty.value = true;
	});

	return {
		letterhead_name,
		print_format,
		letterhead,
		doctype,
		meta,
		layout,
		dirty,
		edit_letterhead,
		scroll_to_section,
		selected_field,
		selected_section,
		selected_letterhead,
		selected_lh_footer,
		preview_doc,
		preview_doc_name,
		load_preview_doc,
		fetch,
		update,
		save_changes,
		reset_changes,
		get_layout,
		get_default_layout,
		change_letterhead,
	};
}

export function useStore() {
	// inject store
	let store = ref(inject("$store"));

	// computed
	let print_format = computed(() => {
		return store.value.print_format;
	});
	let layout = computed(() => {
		return store.value.layout;
	});
	let letterhead = computed(() => {
		return store.value.letterhead;
	});
	let meta = computed(() => {
		return store.value.meta;
	});

	return { print_format, layout, letterhead, meta, store };
}
