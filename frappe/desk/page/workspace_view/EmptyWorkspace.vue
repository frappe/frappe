<script setup>
import { Button } from "frappe-ui";

// A workspace with no blocks yet, read or being built.
defineProps({
	editing: { type: Boolean, default: false },
	can_edit: { type: Boolean, default: false },
});

const emit = defineEmits(["edit", "add-text"]);
const __ = window.__;
</script>

<template>
	<div class="flex flex-col items-center gap-3 py-24 text-center">
		<span class="lucide-layout-grid size-6 text-ink-gray-4" aria-hidden="true" />
		<p class="text-base font-medium text-ink-gray-8">
			{{ editing ? __("Start with a block or some text") : __("This workspace is empty") }}
		</p>
		<p class="max-w-80 text-base text-ink-gray-5">
			{{
				editing
					? __("Pick a chart, card or list from the panel, or add text for a heading.")
					: __("Nothing has been added to it yet.")
			}}
		</p>
		<Button
			v-if="editing"
			icon-left="lucide-type"
			:label="__('Add text')"
			@click="emit('add-text')"
		/>
		<Button
			v-else-if="can_edit"
			icon-left="lucide-pencil"
			:label="__('Edit')"
			@click="emit('edit')"
		/>
	</div>
</template>
