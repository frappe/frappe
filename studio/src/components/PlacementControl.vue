<!-- Extracted from Builder -->
<template>
	<div class="items-top relative flex justify-between">
		<InputLabel class="items-center">Placement</InputLabel>
		<div class="relative h-fit w-fit">
			<div class="dark:bg-zinc-800 group grid grid-cols-3 rounded-sm bg-gray-200 p-1.5">
				<div
					v-for="option in placementOptions"
					:key="option"
					class="group/option flex h-5 w-5 cursor-pointer items-center justify-center opacity-50"
					:class="{
						'!justify-start': option.includes('left'),
						'!justify-end': option.includes('right'),
						'!items-start': option.includes('top'),
						'!items-end': option.includes('bottom'),
					}"
				>
					<div
						@click="setAlignment(option)"
						@dblclick="setAlignment(option, true)"
						class="hidden gap-[2px] opacity-0 hover:opacity-100 group-hover/option:flex"
						:class="{
							'flex-row': direction === 'row',
							'flex-col': direction === 'column',
							'items-center':
								(direction === 'column' &&
									(option === 'top-middle' || option === 'middle-middle' || option === 'bottom-middle')) ||
								(direction === 'row' &&
									(option === 'middle-left' || option === 'middle-middle' || option === 'middle-right')),
							'items-end':
								(direction === 'column' &&
									(option === 'top-right' || option === 'middle-right' || option === 'bottom-right')) ||
								(direction === 'row' &&
									(option === 'bottom-left' || option === 'bottom-middle' || option === 'bottom-right')),
						}"
					>
						<div
							class="dark:bg-zinc-500 rounded-sm bg-gray-500"
							:class="{
								'h-2 w-1': direction === 'row',
								'h-1 w-2': direction === 'column',
							}"
						></div>
						<div
							class="dark:bg-zinc-500 rounded-sm bg-gray-500"
							:class="{
								'h-3 w-1': direction === 'row',
								'h-1 w-3': direction === 'column',
							}"
						></div>
						<div
							class="dark:bg-zinc-500 rounded-sm bg-gray-500"
							:class="{
								'h-2 w-1': direction === 'row',
								'h-1 w-2': direction === 'column',
							}"
						></div>
					</div>
				</div>
			</div>
			<div
				class="pointer-events-none absolute top-0 flex h-full w-full cursor-pointer gap-[2px] rounded-sm p-1.5"
				:style="{
					'flex-direction': direction,
					'justify-content': justifyContent,
					'align-items': alignItems,
				}"
			>
				<div
					class="dark:bg-zinc-400 rounded-sm bg-gray-600"
					:class="{
						'h-1 w-2': direction === 'column',
						'h-2 w-1': direction === 'row',
					}"
				></div>
				<div
					class="dark:bg-zinc-400 rounded-sm bg-gray-600"
					:class="{
						'h-1 w-3': direction === 'column',
						'h-3 w-1': direction === 'row',
					}"
				></div>
				<div
					class="dark:bg-zinc-400 rounded-sm bg-gray-600"
					:class="{
						'h-1 w-2': direction === 'column',
						'h-2 w-1': direction === 'row',
					}"
				></div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import InputLabel from "@/components/InputLabel.vue"
import blockController from "@/utils/blockController"
import { computed } from "vue"

const placementOptions = [
	"top-left",
	"top-middle",
	"top-right",
	"middle-left",
	"middle-middle",
	"middle-right",
	"bottom-left",
	"bottom-middle",
	"bottom-right",
]

const direction = computed(() => blockController.getStyle("flexDirection") as string)
const justifyContent = computed(() => blockController.getStyle("justifyContent") as string)
const alignItems = computed(() => blockController.getStyle("alignItems") as string)

const setAlignment = (alignment: string, spaceBetween: boolean = false) => {
	switch (alignment) {
		case "top-right":
			blockController.setStyle("justifyContent", direction.value === "row" ? "flex-end" : "flex-start")
			blockController.setStyle("alignItems", direction.value === "row" ? "flex-start" : "flex-end")
			break
		case "top-middle":
			blockController.setStyle("justifyContent", direction.value === "row" ? "center" : "flex-start")
			blockController.setStyle("alignItems", direction.value === "row" ? "flex-start" : "center")
			break
		case "top-left":
			blockController.setStyle("justifyContent", "flex-start")
			blockController.setStyle("alignItems", "flex-start")
			break
		case "middle-right":
			blockController.setStyle("justifyContent", direction.value === "row" ? "flex-end" : "center")
			blockController.setStyle("alignItems", direction.value === "row" ? "center" : "flex-end")
			break
		case "middle-middle":
			blockController.setStyle("justifyContent", "center")
			blockController.setStyle("alignItems", "center")
			break
		case "middle-left":
			blockController.setStyle("justifyContent", direction.value === "row" ? "flex-start" : "center")
			blockController.setStyle("alignItems", direction.value === "row" ? "center" : "flex-start")
			break
		case "bottom-right":
			blockController.setStyle("justifyContent", "flex-end")
			blockController.setStyle("alignItems", "flex-end")
			break
		case "bottom-middle":
			blockController.setStyle("justifyContent", direction.value === "row" ? "center" : "flex-end")
			blockController.setStyle("alignItems", direction.value === "row" ? "flex-end" : "center")
			break
		case "bottom-left":
			blockController.setStyle("justifyContent", direction.value === "row" ? "flex-start" : "flex-end")
			blockController.setStyle("alignItems", direction.value === "row" ? "flex-end" : "flex-start")
			break
	}
	if (spaceBetween) {
		blockController.setStyle("justifyContent", "space-between")
	}
}
</script>
