<template>
	<div>
		<div class="flex flex-row flex-wrap gap-4">
			<Input
				label="Page Title"
				type="text"
				variant="outline"
				class="w-full"
				:modelValue="pageTitle"
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
						:hideClearButton="true"
						:modelValue="pageRoute"
						@update:modelValue="
							(val: string) => {
								store.updateActivePage('route', val.startsWith('/') ? val : `/${val}`)
							}
						"
					/>

					<!-- App Route Prefix -->
					<div
						ref="prefixElement"
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
import { computed, nextTick, ref, watch } from "vue"
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

const pageTitle = ref(props.page.page_title || "")
const pageRoute = ref(props.page.route)
const setPageRoute = () => {
	// remove leading slash from route because app route prefix will be <app.route>/ so that user doesn't have to type the leading slash
	pageRoute.value = props.page.route.replace(/^\//, "")
}

const prefixElement = ref<HTMLElement | null>(null)
const dynamicPadding = computed(() => {
	const prefixWidth = (prefixElement.value?.offsetWidth || 0) + 10 // adding 10px for extra space
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
		nextTick(() => {
			// apply dynamic padding to input element when the popover is opened
			// to avoid overlapping with the prefix content
			applyDynamicPadding()
			setPageRoute()
		})
	},
	{ immediate: true },
)
</script>
