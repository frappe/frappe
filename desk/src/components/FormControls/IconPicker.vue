<template>
	<div class="flex flex-col">
		<div v-if="label" class="mb-1.5 text-xs text-gray-600">{{ label }}</div>
		<Popover class="w-full" transition="default" @open="setFocus">
			<template #target="{ togglePopover, isOpen }">
				<Button
					@click="togglePopover()"
					class="flex w-full items-center !justify-start gap-1 truncate text-nowrap"
				>
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
						<div class="relative w-full">
							<TextInput
								ref="searchInput"
								type="text"
								placeholder="Search for icons..."
								v-model="searchText"
								:debounce="200"
								autocomplete="off"
							/>
							<button
								class="absolute right-0 top-0 inline-flex h-7 w-7 items-center justify-center"
								@click="
									() => {
										searchText = ''
										modelValue = ''
										setFocus()
									}
								"
							>
								<FeatherIcon name="x" class="w-4" />
							</button>
						</div>
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

<script setup lang="ts">
import { computed, nextTick, ref } from "vue"
import { Popover, FeatherIcon, TextInput } from "frappe-ui"
import Icon from "@/components/Icon.vue"

withDefaults(defineProps<{ label?: string; placeholder?: string }>(), {
	label: "",
	placeholder: "Select Icon",
})

const modelValue = defineModel("modelValue", {
	type: String,
	default: "",
})
const searchInput = ref("") as unknown as typeof TextInput
const searchText = ref("")

const icons = computed(() => {
	const iconList: string[] = []

	const iconNodeList = searchText.value
		? document.querySelectorAll(`#icons-timeless > symbol[id*="${searchText.value}"]`)
		: document.querySelectorAll("#icons-timeless > symbol[id]")

	iconNodeList.forEach((icon) => {
		iconList.push(icon.id.replace("icon-", ""))
	})
	return iconList
})

const setFocus = () => {
	nextTick(() => searchInput.value?.el.focus())
}
</script>
