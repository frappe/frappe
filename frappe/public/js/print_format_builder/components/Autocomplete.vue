<template>
	<div class="pfb-autocomplete" ref="wrap">
		<div class="pfb-autocomplete-input-wrap" :class="{ focused: open }">
			<span class="pfb-autocomplete-icon" v-html="frappe.utils.icon('search', 'xs')"></span>
			<input
				ref="input_el"
				class="pfb-autocomplete-input"
				type="text"
				:placeholder="placeholder || __('Search...')"
				v-model="query"
				@focus="open = true"
				@input="open = true"
				@blur="on_blur"
				@keydown.escape="open = false"
				@keydown.enter.prevent="confirm_highlight"
				@keydown.down.prevent="highlight = Math.min(highlight + 1, filtered.length - 1)"
				@keydown.up.prevent="highlight = Math.max(highlight - 1, 0)"
			/>
		</div>
		<div v-if="open" class="pfb-autocomplete-dropdown">
			<template v-if="filtered.length">
				<button
					v-for="(opt, i) in filtered"
					:key="opt.value"
					class="pfb-autocomplete-option"
					:class="{ highlighted: highlight === i }"
					@mousedown.prevent="select(opt)"
				>
					<span class="pfb-autocomplete-option-label">{{ opt.label }}</span>
					<span v-if="opt.badge" class="pfb-autocomplete-option-badge">{{
						opt.badge
					}}</span>
				</button>
			</template>
			<div v-else class="pfb-autocomplete-empty">{{ __("No results") }}</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, watch } from "vue";

const props = defineProps({
	options: { type: Array, default: () => [] },
	placeholder: { type: String, default: "" },
});

const emit = defineEmits(["select"]);

const wrap = ref(null);
const input_el = ref(null);
const query = ref("");
const open = ref(false);
const highlight = ref(0);

const filtered = computed(() => {
	const q = query.value.toLowerCase();
	if (!q) return props.options;
	return props.options.filter(
		(o) =>
			(o.label || "").toLowerCase().includes(q) ||
			(o.value || "").toLowerCase().includes(q) ||
			(o.badge || "").toLowerCase().includes(q)
	);
});

watch(filtered, () => {
	highlight.value = 0;
});

function on_blur() {
	setTimeout(() => (open.value = false), 100);
}

function select(opt) {
	emit("select", opt);
	query.value = "";
	open.value = false;
	highlight.value = 0;
}

function confirm_highlight() {
	if (!filtered.value.length) return;
	select(filtered.value[highlight.value] ?? filtered.value[0]);
}

defineExpose({ focus: () => input_el.value?.focus() });
</script>

<style scoped>
.pfb-autocomplete {
	position: relative;
}

.pfb-autocomplete-input-wrap {
	display: flex;
	align-items: center;
	gap: 6px;
	padding: 5px 8px;
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
	background: var(--control-bg);
	transition: border-color 0.1s, background 0.1s;
}

.pfb-autocomplete-input-wrap.focused {
	border-color: var(--gray-500);
	background: var(--fg-color);
}

.pfb-autocomplete-icon {
	display: flex;
	align-items: center;
	color: var(--gray-400);
	flex-shrink: 0;
}

.pfb-autocomplete-input {
	flex: 1;
	border: none;
	background: transparent;
	outline: none;
	font-size: var(--text-sm);
	color: var(--text-color);
	min-width: 0;
}

.pfb-autocomplete-input::placeholder {
	color: var(--gray-400);
}

.pfb-autocomplete-dropdown {
	position: absolute;
	top: calc(100% + 3px);
	left: 0;
	right: 0;
	background: var(--fg-color);
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
	box-shadow: var(--shadow-sm);
	z-index: 100;
	max-height: 200px;
	overflow-y: auto;
}

.pfb-autocomplete-option {
	display: flex;
	align-items: center;
	justify-content: space-between;
	width: 100%;
	padding: 6px 10px;
	border: none;
	background: transparent;
	text-align: left;
	cursor: pointer;
	gap: 8px;
	font-size: var(--text-sm);
}

.pfb-autocomplete-option:hover,
.pfb-autocomplete-option.highlighted {
	background: var(--gray-100);
}

.pfb-autocomplete-option-label {
	flex: 1;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.pfb-autocomplete-option-badge {
	font-size: var(--text-tiny);
	color: var(--gray-500);
	background: var(--gray-100);
	border: 1px solid var(--gray-200);
	border-radius: var(--border-radius-sm);
	padding: 1px 5px;
	white-space: nowrap;
	flex-shrink: 0;
}

.pfb-autocomplete-empty {
	padding: 10px 12px;
	font-size: var(--text-sm);
	color: var(--text-muted);
	text-align: center;
}
</style>
