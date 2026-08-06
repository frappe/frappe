<!--
  Autocomplete — searchable combobox for add-more workflows (no headlessui required)

  Props:
    options     Array<{ label, value, badge? }>   List of options to search through
    placeholder string                            Input placeholder (default: "Search...")
    modelValue  string (optional)                 Single-select mode: the current value is
                                                  shown as the input text when idle, and as
                                                  the placeholder while searching.

  Events:
    @select(opt)   Fired when user picks an option. `opt` is the full option object.
                   Input clears automatically; dropdown stays open for the next pick
                   in add-more mode, and closes in single-select mode.

  Exposes:
    focus()   Programmatically focus the input

  Usage:
    <Autocomplete
      :options="[{ label: 'Item Name', value: 'item_name', badge: 'Data' }]"
      placeholder="Add column..."
      @select="(opt) => add_column(opt.value)"
    />

  Import:
    import Autocomplete from "../../../vue-components/Autocomplete.vue";
-->
<template>
	<div class="frappe-autocomplete">
		<div class="frappe-autocomplete-input-wrap" :class="{ focused }">
			<span
				class="frappe-autocomplete-icon"
				v-html="frappe.utils.icon('search', 'xs')"
			></span>
			<input
				ref="input_el"
				class="frappe-autocomplete-input"
				type="text"
				:placeholder="(focused && display_value) || placeholder || __('Search...')"
				:value="focused ? query : display_value || query"
				@input="query = $event.target.value"
				@focus="focused = true"
				@blur="on_blur"
				@keydown.escape="on_escape"
				@keydown.enter.prevent="confirm_highlight"
				@keydown.down.prevent="highlight = Math.min(highlight + 1, filtered.length - 1)"
				@keydown.up.prevent="highlight = Math.max(highlight - 1, 0)"
			/>
		</div>
		<div v-if="focused" class="frappe-autocomplete-dropdown">
			<template v-if="filtered.length">
				<button
					v-for="(opt, i) in filtered"
					:key="opt.value"
					class="frappe-autocomplete-option"
					:class="{ highlighted: highlight === i }"
					@mousedown.prevent="select(opt)"
				>
					<span class="frappe-autocomplete-option-label">{{ opt.label }}</span>
					<span v-if="opt.badge" class="frappe-autocomplete-option-badge">{{
						opt.badge
					}}</span>
				</button>
			</template>
			<div v-else class="frappe-autocomplete-empty">{{ __("No results") }}</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, watch } from "vue";

const props = defineProps({
	options: { type: Array, default: () => [] },
	placeholder: { type: String, default: "" },
	modelValue: { type: String, default: null },
});

const emit = defineEmits(["select"]);

const input_el = ref(null);
const query = ref("");
const focused = ref(false);
const highlight = ref(0);

const display_value = computed(() => {
	if (props.modelValue == null) return "";
	const opt = props.options.find((o) => o.value === props.modelValue);
	return opt ? opt.label : props.modelValue;
});

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
	setTimeout(() => {
		focused.value = false;
		if (props.modelValue != null) query.value = "";
	}, 100);
}

function on_escape() {
	input_el.value?.blur();
}

function select(opt) {
	emit("select", opt);
	query.value = "";
	highlight.value = 0;
	if (props.modelValue != null) {
		focused.value = false;
		input_el.value?.blur();
	}
}

function confirm_highlight() {
	if (!filtered.value.length) return;
	select(filtered.value[highlight.value] ?? filtered.value[0]);
}

defineExpose({ focus: () => input_el.value?.focus() });
</script>

<style scoped>
.frappe-autocomplete {
	position: relative;
}

.frappe-autocomplete-input-wrap {
	display: flex;
	align-items: center;
	gap: 6px;
	padding: 5px 8px;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--control-bg);
	transition: border-color 0.1s, background 0.1s;
}

.frappe-autocomplete-input-wrap.focused {
	border-color: var(--gray-500);
	background: var(--fg-color);
}

.frappe-autocomplete-icon {
	display: flex;
	align-items: center;
	color: var(--gray-400);
	flex-shrink: 0;
}

.frappe-autocomplete-input {
	flex: 1;
	border: none;
	background: transparent;
	outline: none;
	font-size: var(--text-sm);
	color: var(--text-color);
	min-width: 0;
}

.frappe-autocomplete-input::placeholder {
	color: var(--gray-400);
}

.frappe-autocomplete-dropdown {
	position: absolute;
	top: calc(100% + 3px);
	left: 0;
	right: 0;
	background: var(--fg-color);
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	box-shadow: var(--shadow-sm);
	z-index: 100;
	max-height: 200px;
	overflow-y: auto;
}

.frappe-autocomplete-option {
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

.frappe-autocomplete-option:hover,
.frappe-autocomplete-option.highlighted {
	background: var(--gray-100);
}

.frappe-autocomplete-option-label {
	flex: 1;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.frappe-autocomplete-option-badge {
	font-size: var(--text-tiny);
	color: var(--gray-500);
	background: var(--gray-100);
	border: 1px solid var(--gray-200);
	border-radius: var(--radius);
	padding: 1px 5px;
	white-space: nowrap;
	flex-shrink: 0;
}

.frappe-autocomplete-empty {
	padding: 10px 12px;
	font-size: var(--text-sm);
	color: var(--text-muted);
	text-align: center;
}
</style>
