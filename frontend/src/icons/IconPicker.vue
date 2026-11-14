<!--
  Picks a sprite icon by name. The value is the bare symbol name `fieldtype: Icon` stores, or ""
  for the row's default icon. Attributes such as `label` fall through to the Combobox.
-->
<template>
	<div ref="root" class="w-full">
		<Combobox
			v-bind="$attrs"
			v-model:query="query"
			v-model:open="open"
			trigger="button"
			side="bottom"
			align="start"
			class="w-full"
			:filterable="false"
			:model-value="selected"
			:options="options"
			:placeholder="searching ? currentLabel : __('Search icons')"
			:empty-text="spriteLoaded ? __('No icon matches') : __('Loading icons…')"
			@update:model-value="pick"
		>
			<template #prefix>
				<Icon v-if="modelValue" :name="modelValue" class="text-ink-gray-6" />
			</template>
			<template #item-prefix="{ item }">
				<Icon v-if="item.value" :name="String(item.value)" class="text-ink-gray-6" />
				<!-- keeps "Default icon" on the names' text lane in the list, not in the trigger -->
				<span v-else class="size-4 shrink-0 [[data-slot=trigger]_&]:hidden" />
			</template>
		</Combobox>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Combobox } from "frappe-ui";
import { __ } from "@/i18n";
import Icon from "./Icon.vue";
import { loadSprite, spriteLoaded, symbolNames } from "./sprite";

defineOptions({ inheritAttrs: false });

// The sprite holds ~1.8k names and the list is not virtualised: show the first matches and
// let the search narrow the rest.
const SHOWN = 80;

const props = defineProps<{ modelValue?: string }>();
const emit = defineEmits<{ "update:modelValue": [name: string] }>();

const query = ref("");
const open = ref(false);
const root = ref<HTMLElement>();

loadSprite();

watch(open, (isOpen) => {
	// A pick leaves its name in the query; the next list must not be filtered by it.
	query.value = "";
	if (!isOpen) returnFocus();
});

const needle = computed(() => query.value.trim().toLowerCase().replace(/\s+/g, "-"));

// While searching nothing is selected, so the first match takes the highlight; the trigger
// keeps showing the current icon through `placeholder` and `#prefix`.
const searching = computed(() => needle.value !== "");
const currentLabel = computed(() => props.modelValue || __("Default icon"));
const selected = computed(() => (searching.value ? null : props.modelValue || ""));

const options = computed(() => {
	const shown = rankedMatches(needle.value).slice(0, SHOWN).map(optionFor);
	if (searching.value) return shown;
	const current = props.modelValue;
	if (current && !shown.some((option) => option.value === current)) {
		shown.unshift(optionFor(current));
	}
	return [defaultIcon, ...shown];
});

const defaultIcon = { label: __("Default icon"), value: "" };

function rankedMatches(needle: string) {
	const matches = symbolNames().filter((name) => name.includes(needle));
	return [
		...matches.filter((name) => name.startsWith(needle)),
		...matches.filter((name) => !name.startsWith(needle)),
	];
}

function optionFor(name: string) {
	return { label: name, value: name };
}

function pick(name: string | number | null) {
	if (name !== null) emit("update:modelValue", String(name));
}

// The Combobox does not give focus back when it closes. Restore it only when it was lost
// (a click on another field keeps its own focus).
async function returnFocus() {
	// after the popover has unmounted and released its focus trap
	await new Promise((resolve) => setTimeout(resolve));
	if (document.activeElement && document.activeElement !== document.body) return;
	root.value?.querySelector("button")?.focus();
}
</script>
