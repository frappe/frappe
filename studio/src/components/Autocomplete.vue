<!-- Extracted from Builder -->
<template>
	<ComboboxRoot
		v-model="selectedValue"
		v-model:open="isOpen"
		open-on-click
		open-on-focus
		:reset-search-term-on-blur="false"
	>
		<div class="relative" ref="containerRef">
			<div
				class="group form-input flex h-7 flex-1 items-center gap-2 rounded bg-surface-gray-2 p-0 text-sm text-ink-gray-8 transition-colors focus-within:bg-surface-base focus-within:ring-2 focus-within:ring-outline-gray-3"
			>
				<div v-if="$slots.prefix" class="flex items-center pl-2">
					<slot name="prefix" />
				</div>
				<ComboboxInput
					v-model="searchQuery"
					autocomplete="off"
					@focus="emit('focus')"
					@blur="handleBlur"
					@keydown.enter="handleEnter"
					:display-value="getDisplayValue"
					:placeholder="placeholder"
					class="h-full w-full flex-1 border-none bg-transparent px-0 text-base placeholder:text-ink-gray-4 focus:outline-none focus:ring-0"
					:class="{
						'pl-2': !$slots.prefix,
						'pr-2': !hasValue,
					}"
				/>
				<Button v-if="hasValue" variant="ghost" @click.stop="clearSelection" class="-ml-2">
					<CrossIcon class="h-3 w-3" />
				</Button>
			</div>

			<ComboboxContent
				class="absolute z-10 mt-1 max-h-80 w-full overflow-hidden rounded-lg border bg-surface-base shadow-xl"
			>
				<div class="overflow-y-auto p-1">
					<template v-for="(option, index) in displayOptions" :key="`${option.value}-${index}`">
						<ComboboxSeparator
							v-if="option.value.startsWith('_separator_line')"
							class="bg-outline-gray-2 mx-2 my-1 h-px"
						/>
						<ComboboxLabel
							v-else-if="option.value.startsWith('_separator')"
							class="text-xs-semibold px-2 py-1 text-ink-gray-5"
						>
							{{ option.label }}
						</ComboboxLabel>
						<ComboboxItem
							v-else
							:value="option.value"
							:disabled="option.disabled"
							class="group flex cursor-default select-none items-center gap-2 rounded px-2 py-1.5 text-sm text-ink-gray-9 transition-colors data-[disabled]:pointer-events-none data-[highlighted]:bg-surface-gray-1 data-[disabled]:opacity-50"
						>
							<component v-if="option.prefix" :is="option.prefix" class="h-4 w-4 flex-shrink-0" />
							<span class="w-full flex-1 truncate">{{ option.label }}</span>
							<component
								v-if="option.suffix"
								:is="option.suffix"
								class="h-4 min-w-4 flex-shrink-0 opacity-60 group-hover:opacity-100"
								@mousedown.stop.prevent
								@click.stop.prevent
							/>
						</ComboboxItem>
					</template>
				</div>
				<div v-if="actionButton" class="border-t border-outline-gray-2 bg-surface-gray-1">
					<component v-if="actionButton.component" :is="actionButton.component" @change="refreshOptions" />
					<Button
						v-else
						:icon-left="actionButton.icon"
						variant="ghost"
						class="w-full justify-start rounded-none text-sm"
						@click="actionButton.handler"
					>
						{{ actionButton.label }}
					</Button>
				</div>
			</ComboboxContent>
		</div>
	</ComboboxRoot>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui"
import CrossIcon from "@/components/Icons/Cross.vue"
import {
	ComboboxContent,
	ComboboxInput,
	ComboboxItem,
	ComboboxLabel,
	ComboboxRoot,
	ComboboxSeparator,
} from "reka-ui"
import type { Component } from "vue"
import { computed, ref, watch } from "vue"

interface Option {
	label: string
	value: string
	prefix?: Component
	suffix?: Component
	disabled?: boolean
}

interface ActionButton {
	label: string
	handler: () => void
	icon: string
	component?: Component
}

interface Props {
	options?: Option[]
	getOptions?: (query: string) => Promise<Option[]>
	modelValue?: string | null
	placeholder?: string
	showInputAsOption?: boolean
	actionButton?: ActionButton
	allowArbitraryValue?: boolean
}

const props = withDefaults(defineProps<Props>(), {
	options: () => [],
	placeholder: "Search",
	showInputAsOption: false,
	allowArbitraryValue: true,
})

const emit = defineEmits<{
	"update:modelValue": [value: string | null]
	focus: []
	blur: []
}>()

const containerRef = ref<HTMLElement | null>(null)
const isOpen = ref(false)
const searchQuery = ref("")
const asyncOptions = ref<Option[]>([])
const hasValue = computed(() => props.modelValue != null && props.modelValue !== "")
const allOptions = computed(() => (props.getOptions ? asyncOptions.value : props.options))

const displayOptions = computed(() => {
	let options = allOptions.value
	if (
		props.showInputAsOption &&
		searchQuery.value &&
		!options.some((opt) => opt.value === searchQuery.value)
	) {
		options = [{ label: searchQuery.value, value: searchQuery.value }, ...options]
	}
	return options
})

const selectedValue = computed({
	get: () => props.modelValue,
	set: (value) => {
		emit("update:modelValue", value ?? null)
		isOpen.value = false
	},
})

const getDisplayValue = (item: any): string => {
	if (typeof item === "object") return item?.label || item?.value || ""
	const found = allOptions.value.find((opt) => opt.value === item)
	return found?.label || item || ""
}

const refreshOptions = async (query = "") => {
	if (!props.getOptions) return
	try {
		asyncOptions.value = await props.getOptions(query)
	} catch (error) {
		console.error("Failed to load options:", error)
	}
}

const clearSelection = () => emit("update:modelValue", null)

const getInputValue = (event: Event) => (event.target as HTMLInputElement)?.value?.trim()

const submitArbitraryValue = (inputValue: string) => {
	if (!inputValue) return
	const matchingOption = allOptions.value.find((opt) => opt.label.toLowerCase() === inputValue.toLowerCase())
	emit("update:modelValue", matchingOption?.value ?? inputValue)
	isOpen.value = false
}

const handleEnter = (event: KeyboardEvent) => {
	if (!props.allowArbitraryValue) return
	const highlightedItem = containerRef.value?.querySelector("[data-highlighted]")
	const inputValue = getInputValue(event)
	// If there's a highlighted item and user hasn't typed anything different, let the combobox handle it
	if (highlightedItem && !inputValue) return
	// If user typed something, check if it matches the highlighted item's value
	if (highlightedItem && inputValue) {
		const highlightedValue = highlightedItem.getAttribute("data-value")
		const matchingOption = allOptions.value.find((opt) => opt.value === highlightedValue)
		// If input matches highlighted item's label, let combobox handle it
		if (matchingOption && matchingOption.label.toLowerCase() === inputValue.toLowerCase()) return
	}
	event.preventDefault()
	event.stopPropagation()
	submitArbitraryValue(inputValue)
}

const handleBlur = (event: FocusEvent) => {
	const relatedTarget = event.relatedTarget as HTMLElement
	if (relatedTarget && containerRef.value?.contains(relatedTarget)) {
		emit("blur")
		return
	}
	if (props.allowArbitraryValue) submitArbitraryValue(getInputValue(event))
	emit("blur")
}

watch(searchQuery, (query) => props.getOptions && refreshOptions(query))
watch(
	() => props.modelValue,
	(val) => (searchQuery.value = val ?? ""),
	{ immediate: true },
)
if (props.getOptions) refreshOptions()

defineExpose({
	refreshOptions,
	clearSelection,
})
</script>
