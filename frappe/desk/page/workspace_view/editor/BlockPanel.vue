<script setup>
import { computed } from "vue";
import { Button, TabButtons, TextInput } from "frappe-ui";
import { Link } from "@framework/ui";
import { block_size } from "../grid.js";
import { sizes_of } from "./editor.js";

// The selected block's fields, its size and its removal. Every change applies to the canvas live.
const props = defineProps({
	block: { type: Object, required: true },
	widget: { type: Object, default: null },
});

const emit = defineEmits(["change", "resize", "remove", "close"]);
const __ = window.__;

const TITLES = { number_card: __("Number Card"), chart: __("Chart") };
const LINKS = {
	number_card: { field: "number_card_name", doctype: "Number Card" },
	chart: { field: "chart_name", doctype: "Dashboard Chart" },
};

const link = computed(() => LINKS[props.block.type]);
const size_options = computed(() =>
	sizes_of(props.block.type).map((name) => ({ label: __(name), value: name }))
);
const size = computed({
	get: () => block_size(props.block).name,
	set: (preset) => emit("resize", preset),
});

function set(field, value) {
	props.widget[field] = value;
	emit("change");
}
</script>

<template>
	<aside class="flex w-72 shrink-0 flex-col gap-4 border-l border-outline-gray-1 p-4">
		<div class="flex items-center justify-between">
			<span class="text-base font-medium text-ink-gray-8">
				{{ TITLES[block.type] || __("Block") }}
			</span>
			<Button
				size="sm"
				variant="ghost"
				icon="lucide-x"
				:label="__('Close')"
				@click="emit('close')"
			/>
		</div>
		<template v-if="widget && link">
			<Link
				:label="__(link.doctype)"
				:doctype="link.doctype"
				:model-value="widget[link.field]"
				@update:model-value="(value) => set(link.field, value)"
			/>
			<TextInput
				:label="__('Label')"
				:model-value="widget.label"
				@update:model-value="(value) => set('label', value)"
			/>
		</template>
		<div v-if="size_options.length > 1" class="flex flex-col gap-1.5">
			<span class="text-sm text-ink-gray-5">{{ __("Size") }}</span>
			<TabButtons v-model="size" :options="size_options" />
		</div>
		<Button
			class="self-start"
			theme="red"
			icon-left="lucide-trash-2"
			:label="__('Remove block')"
			@click="emit('remove')"
		/>
	</aside>
</template>
