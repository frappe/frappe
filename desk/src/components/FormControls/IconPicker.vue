<template>
	<div class="flex flex-col">
		<div v-if="label" class="mb-1.5 text-xs text-gray-600">{{ label }}</div>
		<Popover transition="default">
			<template #target="{ togglePopover, isOpen }">
				<Button @click="togglePopover()" class="flex w-28 items-center !justify-start gap-1">
					<template #prefix v-if="modelValue">
						<Icon :name="modelValue" class="h-4 w-4 text-gray-700" />
					</template>
					<span v-if="modelValue">{{ modelValue }}</span>
					<span v-else class="text-base leading-5 text-gray-500">{{ placeholder }}</span>
				</Button>
			</template>

			<template #body>
				<div
					class="mt-2 flex max-h-72 max-w-64 flex-col overflow-y-auto rounded bg-white pb-3 shadow-xl hide-scrollbar"
				>
					<div class="sticky top-0 z-10 bg-white p-3">
						<FormControl
							type="text"
							placeholder="Search for icons..."
							v-model="searchText"
							:debounce="200"
							autocomplete="off"
						/>
					</div>
					<div class="grid grid-cols-8 items-center px-3">
						<button
							v-for="icon in icons"
							:key="icon"
							@click="modelValue = icon"
							:title="icon"
							class="flex h-8 w-8 items-center justify-center rounded-md p-1.5 text-2xl hover:bg-gray-100 focus:outline-none"
						>
							<Icon :name="icon" class="h-5 w-5" />
						</button>
					</div>
				</div>
			</template>
		</Popover>
	</div>
</template>

<script setup>
import { computed, ref } from "vue"
import { Popover } from "frappe-ui"
import Icon from "@/components/Icon.vue"
import FormControl from "frappe-ui/src/components/FormControl.vue"

const props = defineProps({
	label: {
		type: String,
		required: false,
	},
	placeholder: {
		type: String,
		required: false,
		default: "Select Icon",
	},
})

const modelValue = defineModel("modelValue", {
	type: String,
	default: "",
})
const searchText = ref("")

const icons = computed(() => {
	const iconList = []

	const iconNodeList = searchText.value
		? document.querySelectorAll(`#icons-timeless > symbol[id*="${searchText.value}"]`)
		: document.querySelectorAll("#icons-timeless > symbol[id]")

	iconNodeList.forEach((icon) => {
		iconList.push(icon.id.replace("icon-", ""))
	})
	return iconList
})
</script>
