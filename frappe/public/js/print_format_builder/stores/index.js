import {
	ZONE_KEYS,
	clone_plain,
	create_default_layout,
	pluck,
	serialize_layout,
	typst_blockers_client,
} from "../utils";
import { fields, layout_nodes } from "../layout";
import { useConditions } from "../composables/useConditions";
import { useLayoutHistory } from "./useLayoutHistory";
import { usePreviewDoc } from "../composables/usePreviewDoc";
import { useSelection } from "../composables/useSelection";
import { useLayoutMutations } from "../composables/useLayoutMutations";
import { useClipboard } from "../composables/useClipboard";
import { useSnippets } from "../composables/useSnippets";
import { watch, ref, computed, nextTick } from "vue";
import { useDraftSave } from "./useDraftSave";
import { useVersions } from "./useVersions";

export function getStore(print_format_name) {
	// variables
	let print_format = ref(null);
	let viewing_version = ref(null);
	let letterhead = ref(null);
	let meta = ref(null);
	let layout = ref(null);
	let dirty = ref(false);
	let needs_setup = ref(false);
	let scroll_target = ref(null);
	let hovered_field = ref(null);
	let hovered_section = ref(null);
	// the innermost hovered thing wins, so hovering a field doesn't also light up
	// its column and section — one rule, shared by the canvas and the Layers tree
	let hovered_node = computed(() => hovered_field.value || hovered_section.value);
	const selection = useSelection();
	const {
		selected_field,
		selected_fields,
		selected_section,
		selected_sections,
		selected_letterhead,
		selected_lh_footer,
		is_multi_select,
		select_field,
		set_selected,
		set_selection,
		select_section,
		select_letterhead,
		remove_field,
	} = selection;

	// remove everything currently selected — field tombstones + spliced sections
	function remove_selection() {
		selected_fields.value.forEach((df) => (df.remove = true));
		const sections = layout.value?.sections || [];
		selected_sections.value.forEach((s) => {
			const i = sections.indexOf(s);
			if (i !== -1) sections.splice(i, 1);
		});
		selected_fields.value = [];
		selected_field.value = null;
		selected_sections.value = [];
		selected_section.value = null;
	}

	// body fields flattened in layout order — shared by shift-range and marquee select
	function ordered_body_fields() {
		return (layout.value?.sections || []).flatMap((section) => [...fields(section)]);
	}
	function select_field_range(target) {
		const all = ordered_body_fields();
		const ti = all.indexOf(target);
		const ai = selected_field.value ? all.indexOf(selected_field.value) : -1;
		if (ti === -1 || ai === -1) return select_field(target);
		const [lo, hi] = ai <= ti ? [ai, ti] : [ti, ai];
		set_selected(all.slice(lo, hi + 1));
	}
	const {
		duplicate_field,
		duplicate_section,
		duplicate_selection,
		move_selection,
		reflow_dragged_group,
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
	const { condition_state, is_visible } = useConditions(layout, preview_doc);

	// methods
	function fetch() {
		return new Promise((resolve) => {
			frappe.model.clear_doc("Print Format", print_format_name);
			frappe.model.with_doc("Print Format", print_format_name, () => {
				let _print_format = frappe.get_doc("Print Format", print_format_name);
				frappe.model.with_doctype(_print_format.doc_type, () => {
					meta.value = frappe.get_meta(_print_format.doc_type);
					print_format.value = _print_format;
					// the builder edits the draft; what prints stays on the format itself
					// parse_json hands back the raw string when it can't parse
					const parsed = frappe.utils.parse_json(_print_format.draft_data);
					const draft = parsed && typeof parsed === "object" ? parsed : null;
					has_draft.value = !!draft;
					if (draft) Object.assign(print_format.value, draft);
					const saved_layout = get_layout();
					needs_setup.value = !saved_layout;
					const is_classic = Array.isArray(saved_layout);
					const layout_ready = is_classic
						? convert_classic_layout(_print_format)
						: Promise.resolve(saved_layout);
					layout_ready.then((resolved_layout) => {
						const converted = is_classic && !!resolved_layout;
						adopt_layout(resolved_layout);
						selected_field.value = null;
						selected_section.value = null;
						selected_letterhead.value = false;
						selected_lh_footer.value = false;

						const lh_name = layout.value?.letter_head;
						// mirrors the server's get_letterhead: a named letter head loads,
						// "" is an explicit removal, and an absent key falls back to the
						// system default — the canvas must show what the print will use
						let load_lh;
						if (lh_name) {
							load_lh = frappe.db
								.get_doc("Letter Head", lh_name)
								.then((doc) => (letterhead.value = doc))
								.catch(() => (letterhead.value = null));
						} else if (lh_name === "") {
							load_lh = Promise.resolve((letterhead.value = null));
						} else {
							load_lh = frappe.db
								.get_value("Letter Head", { is_default: 1 }, "name")
								.then((r) => {
									const name = r?.message?.name;
									if (!name) return (letterhead.value = null);
									return frappe.db
										.get_doc("Letter Head", name)
										.then((doc) => (letterhead.value = doc));
								})
								.catch(() => (letterhead.value = null));
						}

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
		if (value && typeof value === "object" && value.columns) return pluck(value, ZONE_KEYS);
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
	const {
		undo,
		redo,
		reset: reset_history,
		pause: pause_history,
		can_undo,
		can_redo,
	} = useLayoutHistory(layout, clear_selection);

	function clear_selection() {
		selected_field.value = null;
		selected_section.value = null;
	}
	const {
		saving_count,
		save_failed,
		has_draft,
		save_status,
		call_format,
		after_autosave,
		replace_from_server,
		save_changes,
		save_letterhead,
		autosave,
	} = useDraftSave({
		name: print_format_name,
		print_format,
		letterhead,
		layout,
		dirty,
		viewing_version,
		get_preview_format_doc,
		fetch,
		after_replace: () => history_panel.refresh_if_open(),
	});
	const history_panel = useVersions({
		name: print_format_name,
		print_format,
		dirty,
		viewing_version,
		call_format,
		after_autosave,
		replace_from_server,
		get_preview_format_doc,
		adopt_layout,
		pause_history,
		clear_selection,
	});
	const { forget_version, exit_version, toggle_history, close_history, load_versions } =
		history_panel;
	function discard_draft() {
		forget_version();
		return replace_from_server(
			__("Discarding…"),
			() => call_format("discard_draft", { modified: print_format.value.modified }),
			__("Draft discarded")
		);
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
	function remove_letterhead() {
		letterhead.value = null;
		if (layout.value) {
			// empty string, not delete: marks "user removed it" so the
			// system default is not re-applied on the next load
			layout.value.letter_head = "";
		}
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
	function adopt_layout(resolved) {
		layout.value = resolved || get_default_layout();
		const sections = layout.value.sections;
		layout.value.sections = Array.isArray(sections) ? sections.filter((s) => !s.remove) : [];
		layout.value.header = migrate_to_section(layout.value.header);
		layout.value.footer = migrate_to_section(layout.value.footer);
	}

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
	// letterhead edits flag themselves with _dirty instead of touching `dirty` —
	// route them into the same autosave pipeline
	watch(
		letterhead,
		() => {
			if (letterhead.value?._dirty) dirty.value = true;
		},
		{ deep: true }
	);
	watch(dirty, (v) => v && autosave());

	const typst_blockers = computed(() =>
		typst_blockers_client(print_format.value, layout.value, letterhead.value)
	);
	const has_typst_block = computed(() => {
		for (const node of layout_nodes(layout.value)) {
			if (node.fieldtype === "Typst") return true;
		}
		return false;
	});
	// a blocker added while Typst is selected drops the format back to Chromium,
	// mirroring the server's save-time refusal instead of failing later — unless a
	// Typst block pins the format to Typst, where the blocker itself must go.
	// Lives in the store so the guard stays active while the settings panel is
	// unmounted (a field selection replaces it with the field inspector).
	watch(typst_blockers, (blockers, prev) => {
		if ((blockers || []).join() === (prev || []).join()) return;
		if (!blockers.length || print_format.value?.pdf_generator !== "Typst") return;
		if (has_typst_block.value) {
			frappe.show_alert({
				message: __("This can't be saved with a Typst block: {0}", [blockers.join(", ")]),
				indicator: "orange",
			});
			return;
		}
		print_format.value.pdf_generator = "chrome";
		frappe.show_alert({
			message: __("Switched back to Chromium: {0}", [blockers.join(", ")]),
			indicator: "orange",
		});
	});

	const { clipboard, copy_field, copy_section, copy_selection, paste_clipboard } = useClipboard({
		selection,
		layout,
		insert_section,
		insert_field,
	});
	const { snippets, prompt_snippet, insert_snippet, delete_snippet } = useSnippets({
		insert_section,
		insert_field,
		doc_type: computed(() => print_format.value?.doc_type),
	});

	return {
		print_format,
		letterhead,
		meta,
		layout,
		typst_blockers,
		has_typst_block,
		dirty,
		needs_setup,
		scroll_target,
		hovered_field,
		hovered_section,
		hovered_node,
		selected_field,
		selected_fields,
		remove_selection,
		remove_field,
		selected_section,
		selected_sections,
		selected_letterhead,
		selected_lh_footer,
		is_multi_select,
		preview_doc,
		preview_doc_name,
		condition_state,
		is_visible,
		preview_values,
		preview_child_values,
		load_preview_doc,
		persisted_preview_doc_name,
		fetch,
		draft: {
			saving_count,
			save_failed,
			has_draft,
			status: save_status,
			save: save_changes,
			discard: discard_draft,
		},
		versions: {
			list: history_panel.versions,
			viewing: viewing_version,
			open: history_panel.show_history,
			load: load_versions,
			save: history_panel.save_version,
			remove: history_panel.delete_version,
			restore: history_panel.restore_version,
			view: history_panel.view_version,
			exit: exit_version,
			toggle: toggle_history,
			close: close_history,
		},
		can_undo,
		can_redo,
		get_preview_format_doc,
		select_field,
		set_selected,
		set_selection,
		select_field_range,
		ordered_body_fields,
		reflow_dragged_group,
		select_section,
		select_letterhead,
		remove_section,
		get_default_layout,
		change_letterhead,
		remove_letterhead,
		clipboard,
		copy_field,
		copy_section,
		copy_selection,
		duplicate_field,
		duplicate_section,
		duplicate_selection,
		move_selection,
		snippets,
		prompt_snippet,
		insert_snippet,
		delete_snippet,
		paste_clipboard,
		undo,
		redo,
	};
}
