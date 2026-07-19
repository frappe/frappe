import { ref } from "vue";
import { clone_plain, freshen_field } from "../utils";

const CLIPBOARD_KEY = "pfb_clipboard";

function load_clipboard() {
	try {
		return JSON.parse(localStorage.getItem(CLIPBOARD_KEY)) || null;
	} catch {
		return null;
	}
}
function persist(value) {
	try {
		localStorage.setItem(CLIPBOARD_KEY, JSON.stringify(value));
		return true;
	} catch {
		return false;
	}
}

const clipboard = ref(load_clipboard());
function set_clipboard(value) {
	clipboard.value = value;
	persist(value);
}

if (typeof window !== "undefined") {
	window.addEventListener("storage", (e) => {
		if (e.key === CLIPBOARD_KEY) clipboard.value = load_clipboard();
	});
}

export function useClipboard({ selection, layout, find_field_column, insert_section }) {
	const { selected_field, selected_section } = selection;

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

	return { clipboard, copy_field, copy_section, copy_selection, paste_clipboard };
}
