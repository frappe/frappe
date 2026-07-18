import { create_default_layout, serialize_layout } from "../utils";
import { useLayoutHistory } from "./useLayoutHistory";
import { watch, ref, inject, computed, nextTick } from "vue";

// Copy/paste clipboard — persisted to localStorage so a field or section copied
// in one print format can be pasted into another, even across reloads or tabs.
const CLIPBOARD_KEY = "pfb_clipboard";

function load_clipboard() {
	try {
		return JSON.parse(localStorage.getItem(CLIPBOARD_KEY)) || null;
	} catch {
		return null;
	}
}

const clipboard = ref(load_clipboard());

function set_clipboard(value) {
	clipboard.value = value;
	try {
		localStorage.setItem(CLIPBOARD_KEY, JSON.stringify(value));
	} catch {
		// ignore quota / privacy-mode failures; in-memory copy still works
	}
}

// keep the in-memory copy fresh when another tab copies something
if (typeof window !== "undefined") {
	window.addEventListener("storage", (e) => {
		if (e.key === CLIPBOARD_KEY) clipboard.value = load_clipboard();
	});
}

function clone_plain(obj) {
	return JSON.parse(JSON.stringify(obj));
}

// A pasted custom element (HTML/Image/Barcode block) gets a fresh fieldname so
// duplicates don't collide; real doctype fields keep theirs.
function freshen_field(f) {
	delete f.remove;
	if (f.custom && f.fieldname) f.fieldname += "_" + frappe.utils.get_random(8);
	return f;
}

export function getStore(print_format_name) {
	// variables
	let print_format = ref(null);
	let letterhead = ref(null);
	let doctype = ref(null);
	let meta = ref(null);
	let layout = ref(null);
	let dirty = ref(false);
	let needs_setup = ref(false);
	let edit_letterhead = ref(false);
	let scroll_to_section = ref(null);
	let selected_field = ref(null);
	let selected_section = ref(null);
	let selected_letterhead = ref(false);
	let selected_lh_footer = ref(false);
	let preview_doc = ref(null);
	let preview_doc_name = ref(null);
	let preview_values = ref({});
	let preview_child_values = ref({});
	let preview_load_seq = 0;

	// methods
	function fetch() {
		return new Promise((resolve) => {
			frappe.model.clear_doc("Print Format", print_format_name);
			frappe.model.with_doc("Print Format", print_format_name, () => {
				let _print_format = frappe.get_doc("Print Format", print_format_name);
				frappe.model.with_doctype(_print_format.doc_type, () => {
					meta.value = frappe.get_meta(_print_format.doc_type);
					print_format.value = _print_format;
					const saved_layout = get_layout();
					needs_setup.value = !saved_layout;
					const is_classic = Array.isArray(saved_layout);
					const layout_ready = is_classic
						? convert_classic_layout(_print_format)
						: Promise.resolve(saved_layout);
					layout_ready.then((resolved_layout) => {
						const converted = is_classic && !!resolved_layout;
						layout.value = resolved_layout || get_default_layout();
						layout.value.sections = layout.value.sections.filter((s) => !s.remove);
						layout.value.header = migrate_to_section(layout.value.header);
						layout.value.footer = migrate_to_section(layout.value.footer);
						edit_letterhead.value = false;
						selected_field.value = null;
						selected_section.value = null;
						selected_letterhead.value = false;
						selected_lh_footer.value = false;

						const lh_name = layout.value?.letter_head;
						const load_lh = lh_name
							? frappe.db
									.get_doc("Letter Head", lh_name)
									.then((doc) => (letterhead.value = doc))
							: Promise.resolve((letterhead.value = null));

						load_lh.then(() => {
							reset_history();
							nextTick(() => (dirty.value = converted));
							resolve();
						});
					});
				});
			});
		});
	}
	function convert_classic_layout(_print_format) {
		return frappe
			.call("frappe.printing.doctype.print_format.classic_converter.get_beta_layout", {
				print_format: print_format_name,
			})
			.then((r) => {
				_print_format.classic_format_data = r.message.classic_format_data;
				_print_format.print_format_builder = 0;
				_print_format.print_format_builder_beta = 1;
				_print_format.pdf_generator = "chrome";
				if (_print_format.page_number === "Hide") {
					_print_format.page_number = "Bottom Center";
				}
				if (r.message.dropped.length) {
					frappe.msgprint({
						title: __("Converted from the old Print Format Builder"),
						indicator: "orange",
						message: __(
							"These fields no longer exist in the DocType and were removed from the layout: {0}",
							[r.message.dropped.join(", ")]
						),
					});
				}
				return r.message.layout;
			})
			.catch((e) => {
				console.error("Classic print format conversion failed", e);
				frappe.msgprint({
					title: __("Could not convert this print format"),
					indicator: "red",
					message: __("Starting from the default layout instead."),
				});
				return null;
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

		serialize_layout(layout.value);
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
	function get_preview_format_doc() {
		const snapshot = clone_plain(layout.value);
		serialize_layout(snapshot);
		return { ...print_format.value, format_data: JSON.stringify(snapshot) };
	}
	function select_field(df) {
		selected_field.value = df;
		selected_letterhead.value = false;
		selected_lh_footer.value = false;
	}
	function select_section(section) {
		selected_section.value = section;
		selected_field.value = null;
		selected_letterhead.value = false;
		selected_lh_footer.value = false;
	}
	function select_letterhead({ footer = false } = {}) {
		selected_letterhead.value = !footer;
		selected_lh_footer.value = footer;
		selected_field.value = null;
		selected_section.value = null;
	}
	function remove_section(section) {
		const idx = layout.value.sections.indexOf(section);
		if (idx === -1) return;
		layout.value.sections.splice(idx, 1);
		if (selected_section.value === section) {
			selected_section.value = null;
		}
		if (
			selected_field.value &&
			section.columns.some((c) => c.fields.includes(selected_field.value))
		) {
			selected_field.value = null;
		}
	}
	// Persist the chosen preview record per print format so it survives a refresh
	const preview_doc_ls_key = `pfb:preview_doc:${print_format_name}`;
	function persisted_preview_doc_name() {
		return localStorage.getItem(preview_doc_ls_key);
	}
	function load_preview_doc(name) {
		const seq = ++preview_load_seq;
		if (!name) {
			preview_doc.value = null;
			preview_doc_name.value = null;
			preview_values.value = {};
			preview_child_values.value = {};
			localStorage.removeItem(preview_doc_ls_key);
			return;
		}
		preview_doc_name.value = name;
		localStorage.setItem(preview_doc_ls_key, name);
		frappe.db.get_doc(print_format.value.doc_type, name).then((doc) => {
			if (seq !== preview_load_seq) return;
			preview_doc.value = doc;
		});
		frappe
			.call("frappe.utils.print_format_generator.get_formatted_field_values", {
				doctype: print_format.value.doc_type,
				name,
			})
			.then((r) => {
				if (seq !== preview_load_seq) return;
				preview_values.value = r.message?.values || {};
				preview_child_values.value = r.message?.child || {};
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
	function change_letterhead(_letterhead, { keep_clean = false } = {}) {
		return frappe.db.get_doc("Letter Head", _letterhead).then((doc) => {
			letterhead.value = doc;
			// persist the letter head name inside format_data (layout) so it
			// survives save → reload without needing a separate doctype field
			if (layout.value) {
				layout.value.letter_head = _letterhead;
				if (keep_clean) {
					nextTick(() => (dirty.value = false));
				}
			}
		});
	}

	const {
		undo,
		redo,
		reset: reset_history,
	} = useLayoutHistory(layout, () => {
		selected_field.value = null;
		selected_section.value = null;
	});

	watch(
		layout,
		() => {
			dirty.value = true;
		},
		{ deep: true }
	);
	watch(print_format, () => {
		dirty.value = true;
	});

	function copy_field(df) {
		if (!df) return;
		set_clipboard({ type: "field", data: clone_plain(df) });
	}
	function copy_section(section) {
		if (!section) return;
		set_clipboard({ type: "section", data: clone_plain(section) });
	}
	function copy_selection() {
		if (selected_field.value) copy_field(selected_field.value);
		else if (selected_section.value) copy_section(selected_section.value);
	}
	function find_field_column(df) {
		const lv = layout.value;
		const zones = [lv?.header, lv?.footer, ...(lv?.sections || [])].filter(Boolean);
		for (const section of zones) {
			for (const column of section.columns || []) {
				if (column.fields?.includes(df)) return column;
			}
		}
		return null;
	}
	function paste_clipboard() {
		const clip = load_clipboard() || clipboard.value;
		clipboard.value = clip;
		if (!clip || !layout.value) return;

		if (clip.type === "field") {
			const clone = freshen_field(clone_plain(clip.data));
			// Insert after the selected field in its column; else append to the
			// selected section (or the last body section).
			const col = selected_field.value && find_field_column(selected_field.value);
			if (col) {
				col.fields.splice(col.fields.indexOf(selected_field.value) + 1, 0, clone);
			} else {
				const sections = layout.value.sections || [];
				const target = selected_section.value || sections[sections.length - 1];
				const first_col = target?.columns?.[0];
				if (!first_col) return;
				first_col.fields.push(clone);
			}
			selected_section.value = null;
			selected_field.value = clone;
		} else if (clip.type === "section") {
			const clone = clone_plain(clip.data);
			delete clone.remove;
			(clone.columns || []).forEach((c) => (c.fields || []).forEach(freshen_field));
			const sections = layout.value.sections;
			const idx = selected_section.value ? sections.indexOf(selected_section.value) : -1;
			if (idx !== -1) sections.splice(idx + 1, 0, clone);
			else sections.push(clone);
			selected_field.value = null;
			selected_section.value = clone;
		}
	}

	return {
		print_format,
		letterhead,
		doctype,
		meta,
		layout,
		dirty,
		needs_setup,
		edit_letterhead,
		scroll_to_section,
		selected_field,
		selected_section,
		selected_letterhead,
		selected_lh_footer,
		preview_doc,
		preview_doc_name,
		preview_values,
		preview_child_values,
		load_preview_doc,
		persisted_preview_doc_name,
		fetch,
		update,
		save_changes,
		reset_changes,
		get_preview_format_doc,
		select_field,
		select_section,
		select_letterhead,
		remove_section,
		get_layout,
		get_default_layout,
		change_letterhead,
		clipboard,
		copy_field,
		copy_section,
		copy_selection,
		paste_clipboard,
		undo,
		redo,
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
