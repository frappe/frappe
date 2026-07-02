<!--
  SelectMenu — a single-select dropdown modelled on the frappe-ui dropdown.
  Trigger is a frappe-ui-style control; the floating menu uses the same radius
  as the SettingsDialog (var(--radius)). `options` are strings or {label, value};
  an empty value maps to the placeholder ("clear" choice).
-->
<template>
	<div ref="root" class="cs-select">
		<button type="button" class="cs-select-trigger" :class="{ open }" @click="open = !open">
			<span class="cs-select-label">{{ selectedLabel }}</span>
			<svg class="icon icon-sm cs-select-caret"><use href="#icon-chevron-down"></use></svg>
		</button>

		<div v-if="open" class="cs-select-menu">
			<button
				v-for="option in items"
				:key="option.value"
				type="button"
				class="cs-select-option"
				:class="{ selected: option.value === modelValue }"
				@click="choose(option.value)"
			>
				<span class="cs-select-option-label">{{ option.label }}</span>
				<svg v-if="option.value === modelValue" class="icon icon-xs cs-select-check">
					<use href="#icon-check"></use>
				</svg>
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

const props = defineProps({
	modelValue: { type: String, default: "" },
	options: { type: Array, default: () => [] },
	placeholder: { type: String, default: __("Select") },
});
const emit = defineEmits(["update:modelValue"]);

const root = ref(null);
const open = ref(false);

// The placeholder is the "clear" option; then each provided option.
const items = computed(() => [
	{ label: props.placeholder, value: "" },
	...props.options.map((option) =>
		typeof option === "string" ? { label: option, value: option } : option
	),
]);

const selectedLabel = computed(() => {
	const match = items.value.find((option) => option.value === props.modelValue);
	return match ? match.label : props.placeholder;
});

function choose(value) {
	emit("update:modelValue", value);
	open.value = false;
}

function onOutside(event) {
	if (open.value && root.value && !root.value.contains(event.target)) open.value = false;
}

function onEscape(event) {
	if (event.key === "Escape") open.value = false;
}

onMounted(() => {
	document.addEventListener("mousedown", onOutside);
	document.addEventListener("keydown", onEscape);
});
onBeforeUnmount(() => {
	document.removeEventListener("mousedown", onOutside);
	document.removeEventListener("keydown", onEscape);
});
</script>

<style scoped>
.cs-select {
	position: relative;
	flex-shrink: 0;
}

.cs-select-trigger {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 8px;
	height: 32px;
	padding: 0 10px;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--control-bg);
	color: var(--text-color);
	font-size: var(--text-sm);
	cursor: pointer;
	transition: border-color 0.1s, background 0.1s;
}

.cs-select-trigger:hover,
.cs-select-trigger.open {
	border-color: var(--gray-500);
}

.cs-select-label {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.cs-select-caret {
	flex-shrink: 0;
	color: var(--gray-500);
}

.cs-select-menu {
	position: absolute;
	top: calc(100% + 4px);
	right: 0;
	left: 0;
	z-index: 100;
	padding: 4px;
	background: var(--fg-color);
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	box-shadow: var(--shadow-sm);
	max-height: 240px;
	overflow-y: auto;
}

.cs-select-option {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 8px;
	width: 100%;
	padding: 6px 8px;
	border: none;
	border-radius: calc(var(--radius) - 3px);
	background: transparent;
	color: var(--text-color);
	font-size: var(--text-sm);
	text-align: left;
	cursor: pointer;
}

.cs-select-option:hover {
	background: var(--gray-100);
}

.cs-select-option.selected {
	color: var(--ink-gray-9);
	font-weight: var(--weight-medium);
}

.cs-select-option-label {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.cs-select-check {
	flex-shrink: 0;
	color: var(--ink-gray-7);
}
</style>
