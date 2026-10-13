<template>
	<div class="pfb-settings">
		<InspectorSection :label="__('Typography')">
			<InspectorRow :label="__('Font')">
				<Autocomplete
					:options="font_options"
					:model-value="print_format.font || ''"
					:placeholder="__('Default')"
					@select="(o) => (print_format.font = o.value)"
				/>
			</InspectorRow>
			<InspectorRow :label="__('Font size')">
				<input
					type="number"
					class="form-control form-control-sm pfb-insp-input"
					placeholder="14"
					:value="print_format.font_size"
					@change="(e) => (print_format.font_size = parseFloat(e.target.value) || 14)"
				/>
			</InspectorRow>
		</InspectorSection>

		<InspectorSection :label="__('Style')">
			<InspectorRow v-for="c in color_settings" :key="c.fieldname" :label="c.label">
				<ColorInput
					:fieldname="c.fieldname"
					:model-value="print_format[c.fieldname] || ''"
					:placeholder="__('Default')"
					@update:model-value="(v) => (print_format[c.fieldname] = v || null)"
				/>
			</InspectorRow>
			<ToggleRow
				:label="__('Colon after labels')"
				:model-value="!!print_format.show_label_colon"
				@update:model-value="(v) => (print_format.show_label_colon = v ? 1 : 0)"
			/>
		</InspectorSection>

		<InspectorSection :label="__('Spacing (mm)')">
			<SpacingRow
				:label="__('Margins')"
				:model-value="page_margins"
				@update:model-value="set_margins"
			/>
		</InspectorSection>

		<InspectorSection :label="__('Document')">
			<InspectorRow :label="__('PDF renderer')">
				<template #label>
					<span class="pfb-label-with-hint">
						{{ __("PDF renderer") }}
						<span
							v-if="renderer_hint"
							ref="hint_icon"
							class="pfb-hint-icon"
							v-html="frappe.utils.icon('info', 'xs')"
						></span>
					</span>
				</template>
				<select
					class="form-control form-control-sm pfb-insp-select"
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
			</InspectorRow>
			<InspectorRow :label="__('Letter head')">
				<DeskControl
					:df="letterhead_df"
					:model-value="letterhead?.name || ''"
					@update:model-value="set_letterhead"
				/>
			</InspectorRow>
			<InspectorRow :label="__('Page numbers')">
				<select
					class="form-control form-control-sm pfb-insp-select"
					v-model="print_format.page_number"
				>
					<option v-for="p in page_number_positions" :value="p.value">
						{{ p.label }}
					</option>
				</select>
			</InspectorRow>
		</InspectorSection>

		<InspectorSection :label="__('Custom CSS')" :init-open="false">
			<textarea
				class="form-control form-control-sm pfb-css-input"
				:placeholder="__('.print-format p { margin: 0; }')"
				spellcheck="false"
				rows="8"
				:value="print_format.css || ''"
				@input="(e) => (print_format.css = e.target.value)"
			></textarea>
		</InspectorSection>
	</div>
</template>

<script setup>
import { computed, inject, onMounted, onUnmounted, ref, watch } from "vue";
import Autocomplete from "../../vue-components/Autocomplete.vue";
import ToggleRow from "./inspector/ToggleRow.vue";
import InspectorRow from "./inspector/InspectorRow.vue";
import SpacingRow from "./inspector/SpacingRow.vue";
import InspectorSection from "./inspector/InspectorSection.vue";
import ColorInput from "./inspector/ColorInput.vue";
import DeskControl from "./DeskControl.vue";

let store = inject("$store");
let { print_format, letterhead } = store;
let { typst_blockers, has_typst_block } = store;

let google_fonts = ref([]);

let renderer = computed(() =>
	print_format.value?.pdf_generator === "Typst" ? "Typst" : "chrome"
);
let hint_icon = ref(null);
let renderer_hint = computed(() => {
	if (typst_blockers.value.length) {
		const items = typst_blockers.value.map((b) => "• " + b);
		return [__("Typst cannot render:"), ...items].join("\n");
	}
	if (has_typst_block.value) {
		return __("Chromium unavailable: this format uses a Typst block.");
	}
	return renderer.value === "Typst" ? __("Experimental") : "";
});
let hint_tooltip = null;
watch(
	[hint_icon, renderer_hint],
	([el, text]) => {
		hint_tooltip?.destroy();
		hint_tooltip = null;
		if (!el || !text) return;
		frappe.ui.tooltip(el, { text, text_align: "start" });
		hint_tooltip = $(el).data("es-tooltip");
	},
	{ flush: "post" }
);
onUnmounted(() => hint_tooltip?.destroy());

function set_renderer(value) {
	if (value !== "Typst" && has_typst_block.value) return;
	print_format.value.pdf_generator = value === "Typst" ? "Typst" : "chrome";
}
let font_options = computed(() => [
	{ label: __("Default"), value: "" },
	...google_fonts.value.map((f) => ({ label: f, value: f })),
]);

const MARGIN_FIELDS = {
	top: "margin_top",
	right: "margin_right",
	bottom: "margin_bottom",
	left: "margin_left",
};
let page_margins = computed(() =>
	Object.fromEntries(
		Object.entries(MARGIN_FIELDS).map(([side, f]) => [side, print_format.value[f] ?? 0])
	)
);
function set_margins(sides) {
	for (const [side, f] of Object.entries(MARGIN_FIELDS)) {
		print_format.value[f] = Math.max(0, parseFloat(sides[side]) || 0);
	}
}

let page_number_positions = computed(() => [
	{ label: __("Hide"), value: "Hide" },
	{ label: __("Top Left"), value: "Top Left" },
	{ label: __("Top Center"), value: "Top Center" },
	{ label: __("Top Right"), value: "Top Right" },
	{ label: __("Bottom Left"), value: "Bottom Left" },
	{ label: __("Bottom Center"), value: "Bottom Center" },
	{ label: __("Bottom Right"), value: "Bottom Right" },
]);

// ── colors ─────────────────────────────────────────────────
const color_settings = [
	{ fieldname: "label_color", label: __("Label") },
	{ fieldname: "value_color", label: __("Value") },
];
const letterhead_df = {
	fieldname: "letter_head",
	fieldtype: "Link",
	options: "Letter Head",
	placeholder: __("No letter head"),
};
function set_letterhead(name) {
	if (name === (letterhead.value?.name || "")) return;
	name ? store.change_letterhead(name) : store.remove_letterhead();
}

onMounted(() => {
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
	display: inline-flex;
	align-items: center;
	gap: 4px;
}

.pfb-hint-icon {
	display: inline-flex;
	color: var(--ink-gray-6);
}

.pfb-settings :deep(.pfb-insp-row:not(.pfb-insp-row--toggle)) {
	grid-template-columns: 104px 1fr;
}

.pfb-settings :deep(.frappe-control) {
	margin-bottom: 0;
}

.pfb-css-input {
	font-family: var(--font-family-monospace);
	font-size: var(--text-xs);
	line-height: 1.5;
	resize: vertical;
	min-height: 120px;
	height: auto;
}
</style>
