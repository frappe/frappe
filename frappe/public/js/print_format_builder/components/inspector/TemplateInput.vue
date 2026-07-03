<template>
	<div class="pfb-tpl">
		<div class="table-multiselect pfb-tpl-row" ref="row" @click="focus_last">
			<template v-for="(tok, i) in display" :key="i">
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
					:class="{ 'pfb-tpl-text--fill': i === display.length - 1 }"
					type="text"
					v-model="tok.v"
					:style="i === display.length - 1 ? null : { width: tok.v.length + 'ch' }"
					:placeholder="only_empty_text ? __('Type text…') : ''"
					@input="commit"
					@keydown="on_key($event, i)"
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
			<span v-html="frappe.utils.icon('plus', 'xs')"></span>
			{{ __("Add field") }}
		</button>
	</div>
</template>

<script setup>
import { computed, ref, nextTick, watch } from "vue";
import Autocomplete from "../../../vue-components/Autocomplete.vue";

const adding = ref(false);
const picker = ref(null);
const row = ref(null);
function focus_last(e) {
	if (e.target === row.value) row.value.querySelector(".pfb-tpl-text:last-of-type")?.focus();
}
function open_picker() {
	adding.value = true;
	nextTick(() => picker.value?.querySelector("input")?.focus());
}

const props = defineProps({
	modelValue: { type: Array, required: true },
	fields: { type: Array, default: () => [] },
});

// Keep an editable text slot at the start, end, and between adjacent field
// chips so literal text (e.g. " (", "%)") can always be typed inline. Pure —
// does not mutate its input — so simply displaying an untouched template
// (e.g. a freshly-added column's default `template: []`) never dirties the
// print format on its own; only an actual edit (typing, add/remove) commits
// the normalized shape back to modelValue.
function build_normalized(src) {
	const out = [];
	if (!src.length || src[0].t !== "s") out.push({ t: "s", v: "" });
	src.forEach((tok, i) => {
		out.push(tok);
		if (tok.t === "f" && (!src[i + 1] || src[i + 1].t === "f")) out.push({ t: "s", v: "" });
	});
	if (out[out.length - 1].t !== "s") out.push({ t: "s", v: "" });
	return out;
}

const display = ref(build_normalized(props.modelValue));
watch(
	() => props.modelValue,
	(v) => (display.value = build_normalized(v))
);

function commit() {
	props.modelValue.splice(0, props.modelValue.length, ...display.value);
}

let only_empty_text = computed(
	() => display.value.length === 1 && display.value[0].t === "s" && !display.value[0].v
);

function field_label(fieldname) {
	return props.fields.find((f) => f.value === fieldname)?.label || fieldname;
}
function add_field(opt) {
	if (opt?.value) {
		display.value.push({ t: "f", v: opt.value }, { t: "s", v: "" });
		commit();
	}
	adding.value = false;
}
function on_key(e, i) {
	const inputs = [...row.value.querySelectorAll(".pfb-tpl-text")];
	const pos = inputs.indexOf(e.target);
	const collapsed = e.target.selectionStart === e.target.selectionEnd;
	const at_start = collapsed && e.target.selectionStart === 0;
	const at_end = collapsed && e.target.selectionStart === e.target.value.length;

	if (e.key === "ArrowRight" && at_end && inputs[pos + 1]) {
		e.preventDefault();
		inputs[pos + 1].focus();
		inputs[pos + 1].setSelectionRange(0, 0);
	} else if (e.key === "ArrowLeft" && at_start && inputs[pos - 1]) {
		e.preventDefault();
		const prev = inputs[pos - 1];
		prev.focus();
		prev.setSelectionRange(prev.value.length, prev.value.length);
	} else if (e.key === "Backspace" && at_start && display.value[i - 1]?.t === "f") {
		e.preventDefault();
		const caret = display.value[i - 2]?.v.length ?? 0;
		remove(i - 1);
		focus_slot(Math.max(pos - 1, 0), caret);
	} else if (e.key === "Delete" && at_end && display.value[i + 1]?.t === "f") {
		e.preventDefault();
		const caret = e.target.value.length;
		remove(i + 1);
		focus_slot(pos, caret);
	}
}

function focus_slot(pos, caret) {
	nextTick(() => {
		const input = row.value?.querySelectorAll(".pfb-tpl-text")[pos];
		if (input) {
			input.focus();
			input.setSelectionRange(caret, caret);
		}
	});
}

function remove(i) {
	display.value.splice(i, 1);
	// merge text slots that became adjacent
	const a = display.value;
	for (let j = a.length - 1; j > 0; j--) {
		if (a[j].t === "s" && a[j - 1].t === "s") {
			a[j - 1].v += a[j].v;
			a.splice(j, 1);
		}
	}
	display.value = build_normalized(a);
	commit();
}
</script>

<style scoped>
.pfb-tpl {
	display: flex;
	flex-direction: column;
	gap: 6px;
}
.pfb-tpl-row {
	width: 100%;
	box-sizing: border-box;
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
.pfb-tpl-text--fill {
	flex: 1;
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
