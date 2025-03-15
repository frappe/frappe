<template>
	<div>
		<div class="flex flex-row flex-wrap gap-4">
			<Input
				label="Page Title"
				type="text"
				variant="outline"
				class="w-full"
				:modelValue="page.page_title"
				@update:modelValue="(val: string) => store.updateActivePage('page_title', val)"
			/>

			<div class="flex w-full flex-col gap-1">
				<label class="block text-xs text-gray-600">Page Route</label>
				<div class="relative flex items-stretch">
					<Input
						ref="inputRef"
						type="text"
						variant="outline"
						class="w-full"
						:modelValue="pageRoute"
						:hideClearButton="true"
						@update:modelValue="
							(val: string) => {
								store.updateActivePage('route', val.startsWith('/') ? val : `/${val}`)
							}
						"
					/>

					<!-- App Route Prefix -->
					<div
						class="absolute bottom-[1px] left-[1px] flex items-center rounded-l-[0.4rem] bg-gray-100 text-gray-700"
					>
						<span class="flex h-[1.6rem] items-center text-nowrap px-2 py-0 text-base">
							{{ `${app?.route}/` }}
						</span>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type { StudioApp } from "@/types/Studio/StudioApp"
import Input from "@/components/Input.vue"

const store = useStudioStore()
const props = defineProps<{
	page: StudioPage
	app: StudioApp
	isOpen: boolean
}>()

const inputRef = ref<InstanceType<typeof Input> | null>(null)
const pageRoute = ref(props.page.route)
const setPageRoute = () => {
	// remove leading slash from route because app route prefix will be <app.route>/ so that user doesn't have to type the leading slash
	pageRoute.value = props.page.route.replace(/^\//, "")
}

const dynamicPadding = computed(() => {
	const prefixWidth = props.app?.route?.length * 8 + 15 // Assuming 8px per character plus 4px for padding
	return `${Math.round(prefixWidth)}px`
})

const applyDynamicPadding = () => {
	if (inputRef.value) {
		const inputElement = inputRef.value.$el.querySelector("input")
		if (inputElement) {
			inputElement.style.paddingLeft = dynamicPadding.value
		}
	}
}

watch(
	() => props.isOpen,
	() => {
		// apply dynamic padding to input element when the popover is opened
		// to avoid overlapping with the prefix content
		applyDynamicPadding()
		setPageRoute()
	},
	{ immediate: true },
)
</script>
