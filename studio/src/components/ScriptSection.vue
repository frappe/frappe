<template>
	<div class="border-t border-outline-elevation-2 pt-4">
		<div class="mb-3">
			<div class="mb-2 flex min-h-7 items-center justify-between">
				<h3 class="text-sm-medium text-ink-gray-8">{{ title }}</h3>
				<Button v-if="modelValue" variant="ghost" size="sm" icon="lucide-x" @click="handleRemove" />
			</div>
			<Code
				v-if="modelValue"
				v-model="modelValue"
				language="javascript"
				:emitOnChange="true"
				:completions="completions"
			/>
			<div v-else class="flex flex-col items-center rounded-lg border border-outline-elevation-2 p-4">
				<span v-if="description" class="px-2 py-1 text-center text-sm leading-5 text-ink-gray-4">
					{{ description }}
				</span>
				<button
					class="flex cursor-pointer items-center rounded p-1 text-ink-gray-6 hover:bg-surface-gray-4"
					@click="handleAdd"
				>
					<FeatherIcon name="plus" class="h-3 w-3" />
					<span class="ml-1 text-sm">Add Script</span>
				</button>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui"
import Code from "@/components/Code.vue"
import type { CompletionContext } from "@codemirror/autocomplete"

const modelValue = defineModel<string | null>({ default: null })

const props = withDefaults(
	defineProps<{
		title: string
		description: string
		boilerplate?: string
		completions?: (context: CompletionContext) => any
	}>(),
	{},
)

const handleAdd = () => (modelValue.value = props.boilerplate || "")
const handleRemove = () => (modelValue.value = null)
</script>
