<template>
	<div class="pfb-settings">
		<div class="form-group">
			<label class="control-label">{{ __("Style Preset") }}</label>
			<div class="pfb-preset-row">
				<select
					class="form-control form-control-sm"
					:value="active_preset"
					@change="apply_preset($event.target.value)"
				>
					<option value="">{{ __("Choose a preset…") }}</option>
					<option v-for="p in store.style_presets.value" :key="p.name" :value="p.name">
						{{ p.name }}
					</option>
				</select>
				<button
					class="es-button"
					data-size="sm"
					data-variant="ghost"
					data-icon-button="true"
					:title="__('Save current style as a preset')"
					@click="save_preset"
					v-html="frappe.utils.icon('save', 'sm')"
				></button>
				<button
					v-if="active_preset"
					class="es-button"
					data-size="sm"
					data-variant="ghost"
					data-theme="red"
					data-icon-button="true"
					:title="__('Delete preset')"
					@click="delete_preset"
					v-html="frappe.utils.icon('trash', 'sm')"
				></button>
			</div>
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
			<label class="pfb-check">
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
import { computed, inject, nextTick, onMounted, ref, watch } from "vue";
import Autocomplete from "../../vue-components/Autocomplete.vue";
import { mountColorControl } from "./inspector/useColorControl";
import { useStore } from "../stores";

let store = inject("$store");
let { print_format } = useStore();

let google_fonts = ref([]);
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

// a preset rewrites the colours behind the widgets' backs
watch(
	() => color_settings.map((c) => print_format.value?.[c.fieldname]),
	() => {
		for (const c of color_settings) {
			const ctrl = color_controls[c.fieldname];
			if (!ctrl) continue;
			const model = print_format.value?.[c.fieldname] || "";
			if ((ctrl.get_value() || "") !== model) ctrl.set_value(model);
		}
	}
);

// ── style presets ──────────────────────────────────────────
let active_preset = ref("");

function apply_preset(name) {
	active_preset.value = name;
	if (name) store.apply_style_preset(name);
}

function save_preset() {
	frappe.prompt(
		{
			label: __("Preset name"),
			fieldname: "name",
			fieldtype: "Data",
			reqd: 1,
			default: active_preset.value || "",
		},
		({ name }) => {
			store.save_style_preset(name);
			active_preset.value = name.trim();
			frappe.show_alert({ message: __("Style preset saved"), indicator: "green" });
		},
		__("Save Style Preset"),
		__("Save")
	);
}

function delete_preset() {
	const name = active_preset.value;
	if (!name) return;
	frappe.confirm(__("Delete the style preset '{0}'?", [name]), () => {
		store.delete_style_preset(name);
		active_preset.value = "";
	});
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
.pfb-settings .form-group {
	margin-bottom: 12px;
}

.pfb-settings .form-group:last-child {
	margin-bottom: 0;
}

.pfb-settings :deep(.frappe-control) {
	margin-bottom: 0;
}

.pfb-preset-row {
	display: flex;
	align-items: center;
	gap: 6px;
}

.pfb-preset-row select {
	flex: 1;
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

.pfb-check {
	display: flex;
	align-items: center;
	gap: 6px;
	margin: 0;
	font-size: var(--text-sm);
	cursor: pointer;
}
</style>
