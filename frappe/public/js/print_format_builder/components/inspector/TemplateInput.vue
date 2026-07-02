<template>
	<div class="pfb-tpl">
		<div class="pfb-tpl-row">
			<template v-for="(tok, i) in modelValue" :key="i">
				<span v-if="tok.t === 'f'" class="pfb-tpl-chip">
					{{ field_label(tok.v) }}
					<button
						type="button"
						class="pfb-tpl-x"
						@click="remove(i)"
						v-html="frappe.utils.icon('x', 'xs')"
					></button>
				</span>
				<input
					v-else
					class="pfb-tpl-text"
					type="text"
					v-model="tok.v"
					:size="Math.max((tok.v || '').length, only_empty_text ? 14 : 2)"
					:placeholder="only_empty_text ? __('Type text…') : ''"
				/>
			</template>
		</div>
		<span v-if="!fields.length" class="pfb-tpl-hint">{{
			__("Select a source table first")
		}}</span>
		<select v-else class="pfb-tpl-add" @change="add_field">
			<option value="">{{ __("+ field") }}</option>
			<option v-for="f in fields" :key="f.value" :value="f.value">{{ f.label }}</option>
		</select>
	</div>
</template>

<script setup>
import { computed, onMounted } from "vue";

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
function add_field(e) {
	if (e.target.value) {
		props.modelValue.push({ t: "f", v: e.target.value }, { t: "s", v: "" });
	}
	e.target.value = "";
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
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: 2px;
	min-height: 30px;
	padding: 4px 6px;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--fg-color);
}
.pfb-tpl-chip {
	display: inline-flex;
	align-items: center;
	gap: 2px;
	padding: 1px 3px 1px 6px;
	font-size: var(--text-tiny);
	font-weight: var(--weight-medium);
	color: var(--blue-600);
	background: var(--blue-100);
	border-radius: var(--radius);
	white-space: nowrap;
}
.pfb-tpl-x {
	border: none;
	background: transparent;
	color: inherit;
	cursor: pointer;
	display: inline-flex;
	padding: 0;
}
.pfb-tpl-text {
	border: none;
	outline: none;
	background: transparent;
	font-size: var(--text-sm);
	color: var(--text-color);
	min-width: 12px;
	padding: 0 2px;
}
.pfb-tpl-hint {
	font-size: var(--text-tiny);
	font-style: italic;
	color: var(--text-muted);
}
.pfb-tpl-add {
	align-self: flex-start;
	font-size: var(--text-tiny);
	padding: 2px 6px;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--subtle-accent);
	color: var(--text-muted);
	cursor: pointer;
}
</style>
