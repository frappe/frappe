<template>
	<div class="pfb-settings">
		<InspectorSection :label="__('Document')">
			<div class="form-group">
				<div class="pfb-label-with-hint">
					<label class="control-label">{{ __("PDF Renderer") }}</label>
					<span
						v-if="renderer_hint"
						ref="hint_icon"
						class="pfb-hint-icon"
						v-html="frappe.utils.icon('info', 'xs')"
					></span>
				</div>
				<select
					class="form-control form-control-sm"
					:value="renderer"
					@change="set_renderer($event.target.value)"
				>
					<option value="chrome" :disabled="has_typst_block">
						{{ __("Chromium") }}
					</option>
					<option value="Typst" :disabled="typst_blockers.length > 0">
						{{ __("Typst (fast)") }}
					</option>
				</select>
			</div>
			<div class="form-group">
				<label class="control-label">{{ __("Letter Head") }}</label>
				<div ref="lh_host"></div>
			</div>
		</InspectorSection>

		<InspectorSection :label="__('Text')">
			<div class="form-group">
				<label class="control-label">{{ __("Google Font") }}</label>
				<Autocomplete
					:options="font_options"
					:model-value="print_format.font || ''"
					:placeholder="__('Default')"
					@select="(o) => (print_format.font = o.value)"
				/>
			</div>
			<div class="form-group">
				<label class="control-label">{{ __("Font Size (pt)") }}</label>
				<input
					type="number"
					class="form-control form-control-sm"
					placeholder="12, 13, 14"
					:value="print_format.font_size"
					@change="(e) => (print_format.font_size = parseFloat(e.target.value))"
				/>
			</div>
			<div class="form-group" v-for="c in color_settings" :key="c.fieldname">
				<label class="control-label">{{ c.label }}</label>
				<div :ref="(el) => (color_hosts[c.fieldname] = el)"></div>
			</div>
			<div class="form-group">
				<ToggleRow
					:label="__('Colon after labels')"
					:model-value="!!print_format.show_label_colon"
					@update:model-value="(v) => (print_format.show_label_colon = v ? 1 : 0)"
				/>
			</div>
		</InspectorSection>

		<InspectorSection :label="__('Page')">
			<div class="form-group">
				<label class="control-label">{{ __("Margins (mm)") }}</label>
				<div class="pfb-margin-grid">
					<div class="pfb-margin-cell" v-for="df in margins" :key="df.fieldname">
						<label class="pfb-margin-label control-label">{{ df.label }}</label>
						<input
							type="number"
							class="form-control form-control-sm"
							:value="print_format[df.fieldname]"
							min="0"
							@change="(e) => update_margin(df.fieldname, e.target.value)"
						/>
					</div>
				</div>
			</div>
			<div class="form-group">
				<label class="control-label">{{ __("Page Number") }}</label>
				<select class="form-control form-control-sm" v-model="print_format.page_number">
					<option v-for="p in page_number_positions" :value="p.value">
						{{ p.label }}
					</option>
				</select>
			</div>
		</InspectorSection>

		<InspectorSection :label="__('Style')" :init-open="false">
			<div class="form-group">
				<ToggleRow
					:label="__('Custom CSS')"
					:model-value="css_enabled"
					@update:model-value="toggle_css"
				/>
				<textarea
					v-if="css_enabled"
					class="form-control form-control-sm pfb-css-input"
					:placeholder="__('.print-format p { margin: 0; }')"
					spellcheck="false"
					rows="8"
					:value="print_format.css || ''"
					@input="(e) => (print_format.css = e.target.value)"
				></textarea>
			</div>
		</InspectorSection>
	</div>
</template>

<script setup>
import { computed, inject, nextTick, onMounted, ref, watch } from "vue";
import Autocomplete from "../../vue-components/Autocomplete.vue";
import ToggleRow from "./inspector/ToggleRow.vue";
import InspectorSection from "./inspector/InspectorSection.vue";
import { mountColorControl } from "./inspector/useColorControl";
import { useStore } from "../stores";

let store = inject("$store");
let { print_format, letterhead } = useStore();
let { typst_blockers, has_typst_block } = store;

// ── custom css ─────────────────────────────────────────────
let css_enabled = ref(!!print_format.value.css);
// a discarded draft or re-fetch replaces the doc — the toggle follows it,
// except a toggle the user opened themselves stays open through a doc swap
// (a save with an empty box must not close the panel under them)
let css_manual = false;
watch(
	() => print_format.value,
	(pf) => {
		if (pf?.css) css_enabled.value = true;
		else if (!css_manual) css_enabled.value = false;
	}
);
watch(
	() => print_format.value?.css,
	(v) => {
		if (v) css_enabled.value = true;
	}
);
// turning the toggle off clears the css from the format, but keep what was
// typed so flipping it back on restores it while this panel stays mounted
let stashed_css = "";

function toggle_css(on) {
	css_manual = on;
	css_enabled.value = on;
	if (on) {
		if (stashed_css && !print_format.value.css) {
			print_format.value.css = stashed_css;
		}
	} else {
		stashed_css = print_format.value.css || "";
		print_format.value.css = "";
	}
}

let google_fonts = ref([]);

let renderer = computed(() =>
	print_format.value?.pdf_generator === "Typst" ? "Typst" : "chrome"
);
let hint_icon = ref(null);
let renderer_hint = computed(() => {
	if (typst_blockers.value.length) {
		return __("Typst unavailable: {0}", [typst_blockers.value.join(", ")]);
	}
	if (has_typst_block.value) {
		return __("Chromium unavailable: this format uses a Typst block.");
	}
	return renderer.value === "Typst" ? __("Experimental") : "";
});
watch(
	[hint_icon, renderer_hint],
	([el, title]) => {
		if (!el) return;
		$(el).tooltip("dispose");
		if (title) $(el).tooltip({ title, trigger: "hover", placement: "top" });
	},
	{ flush: "post" }
);
function set_renderer(value) {
	if (value !== "Typst" && has_typst_block.value) return;
	print_format.value.pdf_generator = value === "Typst" ? "Typst" : "chrome";
}
let font_options = computed(() => [
	{ label: __("Default"), value: "" },
	...google_fonts.value.map((f) => ({ label: f, value: f })),
]);

let margins = computed(() => [
	{ label: __("Top"), fieldname: "margin_top" },
	{ label: __("Bottom"), fieldname: "margin_bottom" },
	{ label: __("Left", null, "alignment"), fieldname: "margin_left" },
	{ label: __("Right", null, "alignment"), fieldname: "margin_right" },
]);

let page_number_positions = computed(() => [
	{ label: __("Hide"), value: "Hide" },
	{ label: __("Top Left"), value: "Top Left" },
	{ label: __("Top Center"), value: "Top Center" },
	{ label: __("Top Right"), value: "Top Right" },
	{ label: __("Bottom Left"), value: "Bottom Left" },
	{ label: __("Bottom Center"), value: "Bottom Center" },
	{ label: __("Bottom Right"), value: "Bottom Right" },
]);

function update_margin(fieldname, value) {
	value = parseFloat(value);
	if (value < 0) value = 0;
	print_format.value[fieldname] = value;
}

// ── colors ─────────────────────────────────────────────────
const color_settings = [
	{ fieldname: "label_color", label: __("Label Color") },
	{ fieldname: "value_color", label: __("Value Color") },
];
let color_hosts = ref({});
let color_controls = {};

function mount_color_controls() {
	for (const c of color_settings) {
		const host = color_hosts.value[c.fieldname];
		if (!host) continue;
		color_controls[c.fieldname] = mountColorControl(host, {
			value: print_format.value[c.fieldname] || "",
			placeholder: c.label,
			fieldname: c.fieldname,
			onChange(value) {
				const v = value || null;
				if ((print_format.value[c.fieldname] ?? null) !== v) {
					print_format.value[c.fieldname] = v;
				}
			},
		});
	}
}

// ── letter head ────────────────────────────────────────────
let lh_host = ref(null);
let lh_ctrl = null;

function mount_letterhead_control() {
	if (!lh_host.value) return;
	lh_ctrl = frappe.ui.form.make_control({
		parent: lh_host.value,
		df: {
			fieldname: "letter_head",
			fieldtype: "Link",
			options: "Letter Head",
			placeholder: __("No letter head"),
			change: () => {
				const name = lh_ctrl.get_value() || "";
				if (name === (letterhead.value?.name || "")) return;
				name ? store.change_letterhead(name) : store.remove_letterhead();
			},
		},
		render_input: true,
	});
	lh_ctrl.set_value(letterhead.value?.name || "");
	lh_host.value.querySelector(".control-label")?.remove();
	lh_host.value.querySelector(".form-group")?.style.setProperty("margin", "0");
}

watch(
	() => letterhead.value?.name,
	(name) => lh_ctrl?.set_value(name || "")
);

onMounted(() => {
	nextTick(mount_color_controls);
	nextTick(mount_letterhead_control);
	let method = "frappe.printing.page.print_format_builder.print_format_builder.get_google_fonts";
	frappe.call(method).then((r) => {
		google_fonts.value = r.message || [];
		if (print_format.value.font && !google_fonts.value.includes(print_format.value.font)) {
			google_fonts.value.push(print_format.value.font);
		}
	});
});
</script>

<style scoped>
.pfb-label-with-hint {
	display: flex;
	align-items: center;
	gap: 4px;
}

.pfb-label-with-hint .control-label {
	margin: 0;
}

.pfb-hint-icon {
	display: inline-flex;
	color: var(--text-muted);
}

.pfb-settings .form-group {
	margin-bottom: 12px;
}

.pfb-settings .form-group:last-child {
	margin-bottom: 0;
}

.pfb-settings :deep(.frappe-control) {
	margin-bottom: 0;
}

.pfb-margin-grid {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 6px;
}

.pfb-margin-cell {
	display: flex;
	flex-direction: column;
	gap: 2px;
}

.pfb-margin-label {
	font-size: var(--text-tiny);
}

.pfb-css-input {
	margin-top: 6px;
	font-family: monospace;
	font-size: var(--text-xs);
	line-height: 1.5;
	resize: vertical;
	min-height: 120px;
}
</style>
