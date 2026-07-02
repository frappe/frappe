<template>
	<div class="pfb-tpl">
		<div class="table-multiselect pfb-tpl-row">
			<template v-for="(tok, i) in modelValue" :key="i">
				<span v-if="tok.t === 'f'" class="es-badge">
					{{ field_label(tok.v) }}
					<span
						class="pfb-tpl-x"
						@click="remove(i)"
						v-html="frappe.utils.icon('x', 'xs')"
					></span>
				</span>
				<input
					v-else
					class="pfb-tpl-text"
					type="text"
					v-model="tok.v"
					:style="{ width: (tok.v.length || (only_empty_text ? 12 : 0)) + 'ch' }"
					:placeholder="only_empty_text ? __('Type text…') : ''"
				/>
			</template>
		</div>
		<span v-if="!fields.length" class="pfb-insp-hint text-muted">{{
			__("Select a source table first")
		}}</span>
		<div v-else-if="adding" ref="picker">
			<Autocomplete
				:options="fields"
				:placeholder="__('Search field…')"
				@select="add_field"
			/>
		</div>
		<button v-else type="button" class="pfb-add-btn" @click="open_picker">
			<span v-html="frappe.utils.icon('add', 'xs')"></span>
			{{ __("Add field") }}
		</button>
	</div>
</template>

<script setup>
import { computed, onMounted, ref, nextTick } from "vue";
import Autocomplete from "../../../vue-components/Autocomplete.vue";

const adding = ref(false);
const picker = ref(null);
function open_picker() {
	adding.value = true;
	nextTick(() => picker.value?.querySelector("input")?.focus());
}

const props = defineProps({
	modelValue: { type: Array, required: true },
	fields: { type: Array, default: () => [] },
});

// Keep an editable text slot at the start, end, and between adjacent field
// chips so literal text (e.g. " (", "%)") can always be typed inline.
function normalize() {
	const src = props.modelValue;
	const out = [];
	if (!src.length || src[0].t !== "s") out.push({ t: "s", v: "" });
	src.forEach((tok, i) => {
		out.push(tok);
		if (tok.t === "f" && (!src[i + 1] || src[i + 1].t === "f")) out.push({ t: "s", v: "" });
	});
	if (out[out.length - 1].t !== "s") out.push({ t: "s", v: "" });
	src.splice(0, src.length, ...out);
}
onMounted(normalize);

let only_empty_text = computed(
	() => props.modelValue.length === 1 && props.modelValue[0].t === "s" && !props.modelValue[0].v
);

function field_label(fieldname) {
	return props.fields.find((f) => f.value === fieldname)?.label || fieldname;
}
function add_field(opt) {
	if (opt?.value) props.modelValue.push({ t: "f", v: opt.value }, { t: "s", v: "" });
	adding.value = false;
}
function remove(i) {
	props.modelValue.splice(i, 1);
	// merge text slots that became adjacent
	const a = props.modelValue;
	for (let j = a.length - 1; j > 0; j--) {
		if (a[j].t === "s" && a[j - 1].t === "s") {
			a[j - 1].v += a[j].v;
			a.splice(j, 1);
		}
	}
	normalize();
}
</script>

<style scoped>
.pfb-tpl {
	display: flex;
	flex-direction: column;
	gap: 6px;
}
.pfb-tpl-row {
	align-self: flex-start;
	max-width: 100%;
	min-height: 30px;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--fg-color);
	padding: 4px 6px;
	gap: 0;
}
.pfb-tpl-text {
	border: none;
	outline: none;
	background: transparent;
	font-size: var(--text-sm);
	color: var(--text-color);
	min-width: 0;
	padding: 0;
}
.pfb-tpl-text:focus {
	min-width: 3ch;
}
.pfb-tpl-x {
	display: inline-flex;
	cursor: pointer;
}
.pfb-tpl-row :deep(.es-badge) {
	margin: 1px;
}
</style>
