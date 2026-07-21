import { clone_plain, create_default_layout, serialize_layout } from "../utils";
import { useLayoutHistory } from "./useLayoutHistory";
import { usePresets } from "../composables/usePresets";
import { usePreviewDoc } from "../composables/usePreviewDoc";
import { useSelection } from "../composables/useSelection";
import { useLayoutMutations } from "../composables/useLayoutMutations";
import { useClipboard } from "../composables/useClipboard";
import { useSnippets } from "../composables/useSnippets";
import { watch, ref, inject, computed, nextTick } from "vue";

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
	const selection = useSelection();
	const {
		selected_field,
		selected_fields,
		selected_section,
		selected_letterhead,
		selected_lh_footer,
		select_field,
		select_section,
		select_letterhead,
		remove_selected_fields,
		remove_field,
		align_selected_fields,
	} = selection;
	const {
		duplicate_field,
		duplicate_section,
		duplicate_selection,
		move_selection,
		insert_section,
		insert_field,
		remove_section,
	} = useLayoutMutations(layout, selection);
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

	const { style_presets, save_style_preset, apply_style_preset, delete_style_preset } =
		usePresets(print_format);
	const { clipboard, copy_field, copy_section, copy_selection, paste_clipboard } = useClipboard({
		selection,
		layout,
		insert_section,
		insert_field,
	});
	const {
		snippets,
		save_snippet,
		insert_snippet,
		delete_snippet,
		export_snippets,
		import_snippets,
	} = useSnippets({
		insert_section,
		insert_field,
		doc_type: computed(() => print_format.value?.doc_type),
	});

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
		snippets,
		save_snippet,
		insert_snippet,
		delete_snippet,
		export_snippets,
		import_snippets,
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
