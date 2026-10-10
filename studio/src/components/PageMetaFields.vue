<template>
	<div class="flex w-full flex-col gap-4">
		<Input label="Page Title" type="text" variant="outline" class="w-full" v-model="title" />

		<div class="relative flex w-full items-stretch">
			<Input
				ref="routeInput"
				label="Page Route"
				type="text"
				variant="outline"
				class="w-full"
				:hideClearButton="true"
				:modelValue="route.replace(/^\//, '')"
				@update:modelValue="(value: string) => (route = `/${value.trim().replace(/^\//, '')}`)"
			/>
			<div
				ref="routePrefix"
				class="absolute bottom-[1px] left-[1px] flex items-center rounded-l-[0.4rem] bg-surface-gray-2 text-ink-gray-6"
			>
				<span class="flex h-[1.6rem] items-center text-nowrap px-2 py-0 text-base">{{ `${appRoute}/` }}</span>
			</div>
		</div>

		<Switch
			size="sm"
			class="w-full"
			label="Allow Guest Access"
			description="Anyone can access this page without logging in"
			v-model="allowGuest"
		/>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { useResizeObserver } from "@vueuse/core"
import { Switch } from "frappe-ui"
import Input from "@/components/Input.vue"

defineProps<{ appRoute?: string }>()
const title = defineModel<string>("title", { required: true })
// stored with a leading slash; the input shows it after the app's route prefix
const route = defineModel<string>("route", { required: true })
const allowGuest = defineModel<boolean>("allowGuest", { required: true })

const routeInput = ref<InstanceType<typeof Input> | null>(null)
const routePrefix = ref<HTMLElement | null>(null)

// the prefix sits over the input, so pad the text past it (10px for breathing room)
useResizeObserver(routePrefix, ([entry]) => {
	const input = routeInput.value?.$el.querySelector("input")
	if (input) input.style.paddingLeft = `${Math.round(entry.target.getBoundingClientRect().width) + 10}px`
})
</script>
