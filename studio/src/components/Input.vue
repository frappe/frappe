<template>
	<div class="relative w-full">
		<FormControl
			class="[&>div>input]:focus-visible:ring-zinc-700 [&>div>input]:dark:border-zinc-700 [&>div>input]:dark:bg-zinc-800 [&>div>input]:dark:text-zinc-200 [&>div>input]:dark:focus:border-zinc-600 [&>div>input]:dark:focus:bg-zinc-700 [&>div>input]:dark:focus-visible:ring-zinc-700 [&>div>select]:dark:border-zinc-700 [&>div>select]:dark:bg-zinc-800 [&>div>select]:dark:text-zinc-200 [&>div>select]:dark:focus:bg-zinc-700 relative [&>div>input]:dark:focus-visible:outline-0 [&>div>select]:text-sm [&>div>select]:text-gray-800"
			:type="type"
			:class="{
				'text-sm [&>div>input]:pr-5': !['select', 'checkbox'].includes(type),
			}"
			@change="
				($event: Event) => {
					if (type === 'checkbox') {
						data = ($event.target as HTMLInputElement).checked
					} else {
						data = ($event.target as HTMLInputElement).value
					}
				}
			"
			@input="($event: Event) => (data = ($event.target as HTMLInputElement).value)"
			autocomplete="off"
			v-bind="attrs"
			:modelValue="data"
		></FormControl>
		<div
			class="absolute bottom-[3px] right-[1px] cursor-pointer p-1 text-gray-600"
			@click="clearValue"
			v-if="!['select', 'checkbox'].includes(type) && !hideClearButton"
			v-show="data"
		>
			<CrossIcon />
		</div>
	</div>
</template>

<script setup lang="ts">
import { useAttrs } from "vue"
import CrossIcon from "./Icons/Cross.vue"

const props = withDefaults(
	defineProps<{
		type?: string
		hideClearButton?: boolean
	}>(),
	{
		type: "text",
	},
)

const data = defineModel<string | number | boolean | null>({ default: "" })

defineOptions({
	inheritAttrs: false,
})

const attrs = useAttrs()

const clearValue = () => {
	data.value = ""
}
</script>
