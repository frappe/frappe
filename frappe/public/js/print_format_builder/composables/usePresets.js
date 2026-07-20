import { ref } from "vue";

const STYLE_PRESETS_KEY = "pfb_style_presets";
const STYLE_PRESET_KEYS = [
	"font",
	"font_size",
	"label_color",
	"value_color",
	"margin_top",
	"margin_right",
	"margin_bottom",
	"margin_left",
	"page_number",
];

function load() {
	try {
		return JSON.parse(localStorage.getItem(STYLE_PRESETS_KEY)) || [];
	} catch {
		return [];
	}
}
function persist(list) {
	try {
		localStorage.setItem(STYLE_PRESETS_KEY, JSON.stringify(list));
		return true;
	} catch {
		return false;
	}
}

export function usePresets(print_format) {
	const style_presets = ref(load());
	function save_style_preset(name) {
		name = (name || "").trim();
		if (!name || !print_format.value) return;
		const style = {};
		for (const key of STYLE_PRESET_KEYS) style[key] = print_format.value[key];
		const list = style_presets.value.filter((p) => p.name !== name);
		list.push({ name, style });
		list.sort((a, b) => a.name.localeCompare(b.name));
		style_presets.value = list;
		persist(list);
	}
	function apply_style_preset(name) {
		const preset = style_presets.value.find((p) => p.name === name);
		if (!preset || !print_format.value) return;
		Object.assign(print_format.value, preset.style);
	}
	function delete_style_preset(name) {
		style_presets.value = style_presets.value.filter((p) => p.name !== name);
		persist(style_presets.value);
	}
	return { style_presets, save_style_preset, apply_style_preset, delete_style_preset };
}
