<!-- Extracted from Builder -->
<template>
	<ColorPicker :modelValue="value" @update:modelValue="(color) => emit('change', color)" :property="property">
		<template #target="{ togglePopover, isOpen }">
			<div class="flex items-center justify-between">
				<InputLabel v-if="label">{{ label }}</InputLabel>
				<div class="relative w-full">
					<div
						class="absolute left-2 top-[6px] z-10 h-4 w-4 rounded shadow-sm"
						@click="togglePopover"
						:style="{
							background: value ? value : `url(/assets/builder/images/color-circle.png) center / contain`,
						}"
					></div>
					<Input
						type="text"
						class="[&>div>input]:pl-8"
						placeholder="Set Color"
						:modelValue="displayValue"
						:disabled="disabled"
						@update:modelValue="
							(value: string | null) => {
								value = getRGB(value)
								emit('change', value)
							}
						"
					/>
				</div>
			</div>
		</template>
	</ColorPicker>
</template>
<script setup lang="ts">
import { PropType, computed } from "vue"
import ColorPicker from "@/components/ColorPicker.vue"
import Input from "@/components/Input.vue"
import InputLabel from "@/components/InputLabel.vue"
import { getColorFromToken, getRGB, isColorToken } from "@/utils/helpers"
import type { HashString } from "@/types"

const props = defineProps({
	value: {
		type: String as PropType<HashString | null>,
		default: null,
	},
	label: {
		type: String,
		default: "",
	},
	property: {
		type: String,
		default: "",
	},
})
const emit = defineEmits(["change"])

const displayValue = computed(() => {
	if (!props.value) return ""
	return getColorFromToken(props.value)
})

const disabled = computed(() => isColorToken(props.value))
</script>
