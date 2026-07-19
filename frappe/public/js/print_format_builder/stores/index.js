import { create_default_layout, serialize_layout } from "../utils";
import { useLayoutHistory } from "./useLayoutHistory";
import { usePresets } from "../composables/usePresets";
import { usePreviewDoc } from "../composables/usePreviewDoc";
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

function persist_local(key, value) {
	try {
		localStorage.setItem(key, JSON.stringify(value));
		return true;
	} catch {
		return false;
	}
}

function set_clipboard(value) {
	clipboard.value = value;
	persist_local(CLIPBOARD_KEY, value);
}

if (typeof window !== "undefined") {
	window.addEventListener("storage", (e) => {
		if (e.key === CLIPBOARD_KEY) clipboard.value = load_clipboard();
	});
}

function clone_plain(obj) {
	return JSON.parse(JSON.stringify(obj));
}

const SECTION_SNIPPETS_KEY = "pfb_section_snippets";
function load_section_snippets() {
	try {
		return JSON.parse(localStorage.getItem(SECTION_SNIPPETS_KEY)) || [];
	} catch {
		return [];
	}
}
function persist_section_snippets(list) {
	persist_local(SECTION_SNIPPETS_KEY, list);
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
	let meta = ref(null);
	let layout = ref(null);
	let dirty = ref(false);
	let needs_setup = ref(false);
	let edit_letterhead = ref(false);
	let scroll_to_section = ref(null);
	let selected_field = ref(null);
	let selected_fields = ref([]);
	let selected_section = ref(null);
	let selected_letterhead = ref(false);
	let selected_lh_footer = ref(false);
	const {
		preview_doc,
		preview_doc_name,
		preview_values,
		preview_child_values,
		load_preview_doc,
		persisted_preview_doc_name,
	} = usePreviewDoc(print_format, print_format_name);

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
	function select_field(df, additive = false) {
		if (additive && df) {
			const arr = selected_fields.value.slice();
			const i = arr.indexOf(df);
			if (i === -1) arr.push(df);
			else arr.splice(i, 1);
			selected_fields.value = arr;
			selected_field.value = arr[arr.length - 1] || null;
		} else {
			selected_fields.value = df ? [df] : [];
			selected_field.value = df;
		}
		selected_letterhead.value = false;
		selected_lh_footer.value = false;
	}
	watch(selected_field, (nf) => {
		if (!nf) {
			if (selected_fields.value.length) selected_fields.value = [];
		} else if (!selected_fields.value.includes(nf)) {
			selected_fields.value = [nf];
		}
	});
	function remove_selected_fields() {
		selected_fields.value.forEach((df) => (df.remove = true));
		selected_fields.value = [];
		selected_field.value = null;
	}
	function remove_field(df) {
		df.remove = true;
		const rest = selected_fields.value.filter((f) => f !== df);
		if (rest.length !== selected_fields.value.length) selected_fields.value = rest;
		if (selected_field.value === df) selected_field.value = rest[rest.length - 1] || null;
	}
	function align_selected_fields(align) {
		selected_fields.value.forEach((df) => (df.align = align));
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
	watch(
		print_format,
		() => {
			dirty.value = true;
		},
		{ deep: true }
	);

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
	function duplicate_field(df) {
		if (!df || !layout.value) return;
		const col = find_field_column(df);
		if (!col) return;
		const clone = freshen_field(clone_plain(df));
		col.fields.splice(col.fields.indexOf(df) + 1, 0, clone);
		selected_section.value = null;
		selected_field.value = clone;
	}
	function duplicate_section(section) {
		if (!section || !layout.value) return;
		const sections = layout.value.sections;
		const idx = sections.indexOf(section);
		if (idx === -1) return;
		const clone = clone_plain(section);
		delete clone.remove;
		(clone.columns || []).forEach((c) => (c.fields || []).forEach(freshen_field));
		sections.splice(idx + 1, 0, clone);
		selected_field.value = null;
		selected_section.value = clone;
	}
	function duplicate_selection() {
		if (selected_fields.value.length > 1) {
			const clones = [];
			selected_fields.value.slice().forEach((df) => {
				selected_field.value = null;
				duplicate_field(df);
				if (selected_field.value) clones.push(selected_field.value);
			});
			selected_fields.value = clones;
			selected_field.value = clones[clones.length - 1] || null;
		} else if (selected_field.value) {
			duplicate_field(selected_field.value);
		} else if (selected_section.value) {
			duplicate_section(selected_section.value);
		}
	}
	function move_in_array(arr, item, dir) {
		const i = arr.indexOf(item);
		const j = i + dir;
		if (i === -1 || j < 0 || j >= arr.length) return;
		arr.splice(i, 1);
		arr.splice(j, 0, item);
	}
	function move_fields_in_column(col, fields, dir) {
		const selected = new Set(fields);
		const ordered = fields
			.slice()
			.sort((a, b) => col.fields.indexOf(a) - col.fields.indexOf(b));
		const seq = dir > 0 ? ordered.reverse() : ordered;
		for (const df of seq) {
			const i = col.fields.indexOf(df);
			const j = i + dir;
			if (j < 0 || j >= col.fields.length) continue;
			if (selected.has(col.fields[j])) continue;
			move_in_array(col.fields, df, dir);
		}
	}
	function move_selection(dir) {
		if (selected_fields.value.length > 1) {
			const groups = new Map();
			selected_fields.value.forEach((df) => {
				const col = find_field_column(df);
				if (!col) return;
				if (!groups.has(col)) groups.set(col, []);
				groups.get(col).push(df);
			});
			groups.forEach((fields, col) => move_fields_in_column(col, fields, dir));
		} else if (selected_field.value) {
			const col = find_field_column(selected_field.value);
			if (col) move_in_array(col.fields, selected_field.value, dir);
		} else if (selected_section.value) {
			move_in_array(layout.value?.sections || [], selected_section.value, dir);
		}
	}

	const { style_presets, save_style_preset, apply_style_preset, delete_style_preset } =
		usePresets(print_format);
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
			insert_section(clip.data);
		}
	}
	function insert_section(data) {
		if (!data || !layout.value) return;
		const clone = clone_plain(data);
		delete clone.remove;
		(clone.columns || []).forEach((c) => (c.fields || []).forEach(freshen_field));
		const sections = layout.value.sections;
		const idx = selected_section.value ? sections.indexOf(selected_section.value) : -1;
		if (idx !== -1) sections.splice(idx + 1, 0, clone);
		else sections.push(clone);
		selected_field.value = null;
		selected_section.value = clone;
	}

	const section_snippets = ref(load_section_snippets());
	function save_section_snippet(name, section) {
		name = (name || "").trim();
		if (!name || !section) return;
		const list = section_snippets.value.filter((s) => s.name !== name);
		list.push({ name, section: clone_plain(section) });
		list.sort((a, b) => a.name.localeCompare(b.name));
		section_snippets.value = list;
		persist_section_snippets(list);
	}
	function insert_section_snippet(name) {
		const snip = section_snippets.value.find((s) => s.name === name);
		if (snip) insert_section(snip.section);
	}
	function delete_section_snippet(name) {
		section_snippets.value = section_snippets.value.filter((s) => s.name !== name);
		persist_section_snippets(section_snippets.value);
	}

	return {
		print_format,
		letterhead,
		meta,
		layout,
		dirty,
		needs_setup,
		edit_letterhead,
		scroll_to_section,
		selected_field,
		selected_fields,
		remove_selected_fields,
		remove_field,
		align_selected_fields,
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
		duplicate_field,
		duplicate_section,
		duplicate_selection,
		move_selection,
		style_presets,
		save_style_preset,
		apply_style_preset,
		delete_style_preset,
		section_snippets,
		save_section_snippet,
		insert_section_snippet,
		delete_section_snippet,
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
