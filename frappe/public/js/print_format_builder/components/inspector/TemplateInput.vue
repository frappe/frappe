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
					:size="Math.max((tok.v || '').length, 1)"
					:placeholder="__('text')"
					@blur="drop_if_empty(i)"
				/>
			</template>
			<span v-if="!modelValue.length" class="pfb-tpl-empty">{{
				__("Add fields and text…")
			}}</span>
		</div>
		<div class="pfb-tpl-controls">
			<select class="pfb-tpl-add" @change="add_field">
				<option value="">{{ __("+ field") }}</option>
				<option v-for="f in fields" :key="f.value" :value="f.value">{{ f.label }}</option>
			</select>
			<button type="button" class="pfb-tpl-add" @click="add_text">{{ __("+ text") }}</button>
		</div>
	</div>
</template>

<script setup>
const props = defineProps({
	modelValue: { type: Array, required: true },
	fields: { type: Array, default: () => [] },
});

function field_label(fieldname) {
	return props.fields.find((f) => f.value === fieldname)?.label || fieldname;
}
function add_field(e) {
	if (e.target.value) props.modelValue.push({ t: "f", v: e.target.value });
	e.target.value = "";
}
function add_text() {
	props.modelValue.push({ t: "s", v: "" });
}
function remove(i) {
	props.modelValue.splice(i, 1);
}
function drop_if_empty(i) {
	const tok = props.modelValue[i];
	if (tok && tok.t === "s" && !tok.v) props.modelValue.splice(i, 1);
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
	gap: 4px;
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
	min-width: 8px;
	padding: 0 2px;
}
.pfb-tpl-empty {
	font-size: var(--text-sm);
	font-style: italic;
	color: var(--text-muted);
}
.pfb-tpl-controls {
	display: flex;
	gap: 6px;
}
.pfb-tpl-add {
	font-size: var(--text-tiny);
	padding: 2px 6px;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--subtle-accent);
	color: var(--text-muted);
	cursor: pointer;
}
</style>
