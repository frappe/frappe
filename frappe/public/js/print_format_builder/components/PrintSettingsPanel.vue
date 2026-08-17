<template>
	<div class="pfb-settings">
		<div class="form-group">
			<label class="control-label">{{ __("PDF Renderer") }}</label>
			<select
				class="form-control form-control-sm"
				:value="renderer"
				@change="set_renderer($event.target.value)"
			>
				<option value="chrome" :disabled="has_typst_block">{{ __("Chromium") }}</option>
				<option value="Typst" :disabled="typst_blockers.length > 0">
					{{ __("Typst (fast)") }}
				</option>
			</select>
			<p v-if="typst_blockers.length" class="pfb-renderer-hint">
				{{ __("Typst unavailable:") }} {{ typst_blockers.join(", ") }}
			</p>
			<p v-else-if="has_typst_block" class="pfb-renderer-hint">
				{{ __("Chromium unavailable: this format uses a Typst block.") }}
			</p>
			<p v-else-if="renderer === 'Typst'" class="pfb-renderer-hint">
				{{ __("Experimental") }}
			</p>
		</div>

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
			<label class="control-label">{{ __("Page Margins (mm)") }}</label>
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
			<label class="pfb-insp-check">
				<input
					type="checkbox"
					:checked="!!print_format.show_label_colon"
					@change="(e) => (print_format.show_label_colon = e.target.checked ? 1 : 0)"
				/>
				{{ __("Show colon after labels") }}
			</label>
		</div>

		<div class="form-group">
			<label class="control-label">{{ __("Page Number") }}</label>
			<select class="form-control form-control-sm" v-model="print_format.page_number">
				<option v-for="p in page_number_positions" :value="p.value">{{ p.label }}</option>
			</select>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, nextTick, onMounted, ref } from "vue";
import Autocomplete from "../../vue-components/Autocomplete.vue";
import { mountColorControl } from "./inspector/useColorControl";
import { useStore } from "../stores";

let store = inject("$store");
let { print_format } = useStore();
let { typst_blockers, has_typst_block } = store;

let google_fonts = ref([]);

let renderer = computed(() =>
	print_format.value?.pdf_generator === "Typst" ? "Typst" : "chrome"
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

onMounted(() => {
	nextTick(mount_color_controls);
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
.pfb-renderer-hint {
	margin: 6px 0 0;
	font-size: var(--text-tiny);
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
</style>
