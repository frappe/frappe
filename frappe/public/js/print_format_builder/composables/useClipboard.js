import { ref } from "vue";
import { clone_plain, read_json, write_json } from "../utils";

const CLIPBOARD_KEY = "pfb_clipboard";

const clipboard = ref(read_json(CLIPBOARD_KEY));
function set_clipboard(value) {
	clipboard.value = value;
	write_json(CLIPBOARD_KEY, value);
}

if (typeof window !== "undefined") {
	window.addEventListener("storage", (e) => {
		if (e.key === CLIPBOARD_KEY) clipboard.value = read_json(CLIPBOARD_KEY);
	});
}

export function useClipboard({ selection, layout, insert_section, insert_field }) {
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
		const clip = read_json(CLIPBOARD_KEY) || clipboard.value;
		clipboard.value = clip;
		if (!clip || !layout.value) return;

		if (clip.type === "field") {
			insert_field(clip.data);
		} else if (clip.type === "section") {
			insert_section(clip.data);
		}
	}

	return { clipboard, copy_field, copy_section, copy_selection, paste_clipboard };
}
