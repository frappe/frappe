<!-- Extracted from Builder -->
<template>
	<div class="flex w-full flex-col items-center gap-5">
		<OptionToggle
			:modelValue="position"
			@update:modelValue="position = $event"
			:options="[
				{ label: 'Auto', value: 'static' },
				{ label: 'Free', value: 'absolute' },
				{
					label: 'Fixed',
					value: 'fixed',
				},
				{ label: 'Sticky', value: 'sticky' },
			]"
		></OptionToggle>
		<div class="grid-rows grid grid-cols-3 gap-4" v-if="showHandler">
			<div class="col-span-1 col-start-2 w-16 self-center">
				<Input
					type="text"
					placeholder="top"
					:modelValue="blockController.getStyle('top') as string"
					@update:modelValue="(value: string) => blockController.setStyle('top', value)"
				/>
			</div>
			<div class="col-span-1 col-start-1 w-16 self-center">
				<Input
					type="text"
					placeholder="left"
					:modelValue="blockController.getStyle('left') as string"
					@update:modelValue="(value: string) => blockController.setStyle('left', value)"
				/>
			</div>
			<div
				class="grid-col-3 dark:bg-zinc-800 grid h-16 w-16 grid-rows-3 gap-1 self-center justify-self-center rounded bg-gray-50 p-2"
			>
				<div
					class="col-span-3 row-start-1 h-2 w-[2px] self-center justify-self-center rounded bg-gray-100"
				></div>
				<div
					class="col-span-3 row-start-3 h-2 w-[2px] self-center justify-self-center rounded bg-gray-100"
				></div>
				<div class="h-5 w-5 self-center justify-self-center rounded bg-gray-400"></div>
				<div
					class="col-span-1 col-start-1 row-start-2 h-[2px] w-2 self-center justify-self-center rounded bg-gray-100"
				></div>
				<div
					class="col-span-1 col-start-3 row-start-2 h-[2px] w-2 self-center justify-self-center rounded bg-gray-100"
				></div>
			</div>
			<div class="col-span-1 col-start-3 w-16 self-center">
				<!-- prettier-ignore -->
				<Input
					type="text"
					placeholder="right"
					:modelValue="(blockController.getStyle('right') as string)"
					@update:modelValue="(value: string) => blockController.setStyle('right', value)" />
			</div>
			<div class="col-span-1 col-start-2 w-16 self-center">
				<!-- prettier-ignore -->
				<Input
					type="text"
					placeholder="bottom"
					:modelValue="(blockController.getStyle('bottom') as string)"
					@update:modelValue="(value: string) => blockController.setStyle('bottom', value)" />
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import OptionToggle from "@/components/OptionToggle.vue"
import blockController from "@/utils/blockController"
import { computed, watch } from "vue"

const position = computed({
	get() {
		const pos = (blockController.getStyle("position") as string) || "static"
		if (["relative", "static"].includes(pos)) {
			return "static"
		}
		return pos
	},
	set(value: string) {
		if (value === "static") {
			value = ""
		}
		blockController.setStyle("position", value)
		const parentBlock = blockController.getParentBlock()
		if (parentBlock) {
			parentBlock.setStyle("position", "relative")
		}
	},
})

watch(position, (value) => {
	if (value === "static") {
		blockController.setStyle("top", "")
		blockController.setStyle("left", "")
		blockController.setStyle("right", "")
		blockController.setStyle("bottom", "")
	}
})

const showHandler = computed(() => {
	return ["absolute", "fixed", "sticky"].includes(position.value)
})
</script>
