<script setup>
import { Button } from "frappe-ui";

// A workspace with no blocks yet, read or being built, or one whose blocks the reader cannot see.
defineProps({
	editing: { type: Boolean, default: false },
	can_edit: { type: Boolean, default: false },
	no_access: { type: Boolean, default: false },
	title: { type: String, default: "" },
});

const emit = defineEmits(["edit", "add-text"]);
const __ = window.__;
</script>

<template>
	<div v-if="no_access" class="flex flex-col items-center gap-3 py-24 text-center">
		<div class="flex size-12 items-center justify-center rounded-full bg-surface-gray-2">
			<span class="lucide-key-round size-5 text-ink-gray-6" aria-hidden="true" />
		</div>
		<p class="text-lg font-medium text-ink-gray-8">
			{{ __("Almost there") }}
		</p>
		<p class="max-w-96 text-base leading-relaxed text-ink-gray-5">
			{{
				__(
					"You can open {0}, but what lives inside it needs a little more access. Ask your System Manager to let you in, and this page will fill up.",
					[title]
				)
			}}
		</p>
	</div>
	<div v-else class="flex flex-col items-center gap-3 py-24 text-center">
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
