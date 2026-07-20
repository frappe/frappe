import { ref } from "vue";
import { clone_plain } from "../utils";

const SECTION_SNIPPETS_KEY = "pfb_section_snippets";

function load() {
	try {
		return JSON.parse(localStorage.getItem(SECTION_SNIPPETS_KEY)) || [];
	} catch {
		return [];
	}
}
function persist(list) {
	try {
		localStorage.setItem(SECTION_SNIPPETS_KEY, JSON.stringify(list));
		return true;
	} catch {
		return false;
	}
}

export function useSnippets({ insert_section }) {
	const section_snippets = ref(load());
	function save_section_snippet(name, section) {
		name = (name || "").trim();
		if (!name || !section) return;
		const list = section_snippets.value.filter((s) => s.name !== name);
		list.push({ name, section: clone_plain(section) });
		list.sort((a, b) => a.name.localeCompare(b.name));
		section_snippets.value = list;
		persist(list);
	}
	function insert_section_snippet(name) {
		const snip = section_snippets.value.find((s) => s.name === name);
		if (snip) insert_section(snip.section);
	}
	function delete_section_snippet(name) {
		section_snippets.value = section_snippets.value.filter((s) => s.name !== name);
		persist(section_snippets.value);
	}
	return {
		section_snippets,
		save_section_snippet,
		insert_section_snippet,
		delete_section_snippet,
	};
}
