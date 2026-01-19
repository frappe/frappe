<template>
	<ListboxRoot
		class="flex flex-col overflow-hidden rounded-lg bg-surface-white p-2 text-ink-gray-5"
		:class="{ 'border border-outline-gray-2 shadow-sm': !borderLess }"
		v-model="model"
		@keydown="focusSearchInput"
	>
		<ListboxFilter
			:as="TextInput"
			variant="outline"
			placeholder="Search"
			ref="searchInput"
			:autoFocus="true"
		/>
		<ListboxContent class="max-h-48 overflow-auto pt-1">
			<ListboxItem
				v-for="option in options"
				:key="option.label"
				:value="option.value"
				class="relative flex h-[28px] w-full select-none items-center rounded px-2 text-sm leading-none text-ink-gray-9 outline-none"
			>
				<slot name="option-prefix" v-bind="{ option }"></slot>
				<span>{{ option.label }}</span>
				<ListboxItemIndicator :as="LucideCheck" class="ml-auto size-4" />
			</ListboxItem>
		</ListboxContent>
	</ListboxRoot>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue"
import { TextInput } from "frappe-ui"
import { ListboxContent, ListboxItem, ListboxItemIndicator, ListboxRoot, ListboxFilter } from "reka-ui"
import LucideCheck from "~icons/lucide/check"

type Option = {
	label: string
	value: string
	disabled?: boolean
}

const props = defineProps<{
	borderLess?: boolean
	options?: Option[]
}>()

const model = defineModel<string | null>()

const searchInput = ref<InstanceType<typeof TextInput>>()
const focusSearchInput = () => {
	const input = searchInput.value?.querySelector?.("input") || searchInput.value
	if (input && "focus" in input && typeof input.focus === "function") {
		input.focus()
	}
}
</script>
