<template>
	<div class="pfb-tpl">
		<div class="table-multiselect pfb-tpl-row" ref="row" @click="focus_last">
			<template v-for="(tok, i) in display" :key="i">
				<span v-if="tok.t === 'f'" class="es-badge">
					{{ field_label(tok.v) }}
					<span
						class="es-badge__affix"
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
					:placeholder="only_empty_text ? __('Type text, / for a field') : ''"
					@input="on_input($event, i)"
					@keydown="on_key($event, i)"
					@blur="close_slash"
				/>
			</template>
		</div>
		<ul v-if="slash" class="dropdown-menu show pfb-tpl-menu">
			<li v-for="(f, k) in slash_matches" :key="f.value">
				<a
					class="dropdown-item"
					:class="{ highlighted: k === slash.highlight }"
					href="#"
					@mousedown.prevent="pick(f)"
					@click.prevent="pick(f)"
				>
					{{ f.label }}
				</a>
			</li>
			<li v-if="!slash_matches.length" class="dropdown-item text-muted">
				{{ __("No matching field") }}
			</li>
		</ul>
	</div>
</template>

<script setup>
import { computed, ref, nextTick, watch } from "vue";

const row = ref(null);
const slash = ref(null);
function focus_last(e) {
	if (e.target === row.value) row.value.querySelector(".pfb-tpl-text:last-of-type")?.focus();
}

const props = defineProps({
	modelValue: { type: Array, required: true },
	fields: { type: Array, default: () => [] },
});

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

let slash_matches = computed(() => {
	if (!slash.value) return [];
	const q = slash.value.query.toLowerCase();
	return props.fields.filter(
		(f) => !q || f.label.toLowerCase().includes(q) || f.value.toLowerCase().includes(q)
	);
});

function on_input(e, i) {
	const value = e.target.value;
	const caret = e.target.selectionStart;
	if (slash.value && slash.value.i === i && value[slash.value.start] === "/") {
		slash.value.query = value.slice(slash.value.start + 1, caret);
		slash.value.highlight = 0;
	} else if (props.fields.length && value[caret - 1] === "/") {
		slash.value = { i, start: caret - 1, query: "", highlight: 0 };
	} else {
		slash.value = null;
	}
	commit();
}

function close_slash() {
	slash.value = null;
}

function pick(f) {
	if (!slash.value) return;
	const { i, start, query } = slash.value;
	const text = display.value[i].v;
	const pos = display.value.slice(0, i).filter((t) => t.t === "s").length;
	display.value.splice(
		i,
		1,
		{ t: "s", v: text.slice(0, start) },
		{ t: "f", v: f.value },
		{ t: "s", v: text.slice(start + 1 + query.length) }
	);
	display.value = build_normalized(display.value);
	slash.value = null;
	commit();
	focus_slot(pos + 1, 0);
}

function on_key(e, i) {
	if (slash.value) {
		const n = slash_matches.value.length;
		if (e.key === "ArrowDown" && n) {
			e.preventDefault();
			slash.value.highlight = (slash.value.highlight + 1) % n;
			return;
		}
		if (e.key === "ArrowUp" && n) {
			e.preventDefault();
			slash.value.highlight = (slash.value.highlight - 1 + n) % n;
			return;
		}
		if (e.key === "Enter" && n) {
			e.preventDefault();
			pick(slash_matches.value[slash.value.highlight]);
			return;
		}
		if (e.key === "Escape") {
			e.preventDefault();
			slash.value = null;
			return;
		}
	}
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
	position: relative;
}
.pfb-tpl-menu {
	position: absolute;
	top: calc(100% + 4px);
	left: 0;
	right: 0;
	max-height: 200px;
	overflow-y: auto;
}
.pfb-tpl-menu .dropdown-item.highlighted {
	background: var(--surface-gray-2);
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
.pfb-tpl-row :deep(.es-badge) {
	margin: 1px;
}
.pfb-tpl-row :deep(.es-badge__affix) {
	cursor: pointer;
}
</style>
