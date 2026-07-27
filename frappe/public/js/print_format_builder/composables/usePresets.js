import { ref } from "vue";
import { read_json, write_json } from "../utils";

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

export function usePresets(print_format) {
	const style_presets = ref(read_json(STYLE_PRESETS_KEY, []));
	function save_style_preset(name) {
		name = (name || "").trim();
		if (!name || !print_format.value) return;
		const style = {};
		for (const key of STYLE_PRESET_KEYS) style[key] = print_format.value[key];
		const list = style_presets.value.filter((p) => p.name !== name);
		list.push({ name, style });
		list.sort((a, b) => a.name.localeCompare(b.name));
		style_presets.value = list;
		write_json(STYLE_PRESETS_KEY, list);
	}
	function apply_style_preset(name) {
		const preset = style_presets.value.find((p) => p.name === name);
		if (!preset || !print_format.value) return;
		Object.assign(print_format.value, preset.style);
	}
	function delete_style_preset(name) {
		style_presets.value = style_presets.value.filter((p) => p.name !== name);
		write_json(STYLE_PRESETS_KEY, style_presets.value);
	}
	return { style_presets, save_style_preset, apply_style_preset, delete_style_preset };
}
