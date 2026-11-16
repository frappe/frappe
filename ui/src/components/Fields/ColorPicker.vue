<template>
	<div class="grid grid-cols-7 gap-1.5 p-2" data-slot="color-picker">
		<button
			v-for="swatch in SWATCHES"
			:key="swatch"
			type="button"
			data-slot="swatch-option"
			:aria-label="swatch"
			:aria-pressed="swatch === selected"
			class="size-5 rounded-full border border-outline-gray-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
			:class="swatch === selected && 'ring-2 ring-outline-gray-5'"
			:style="{ backgroundColor: swatch }"
			@click="emit('pick', swatch)"
		/>
		<label
			class="relative grid size-5 cursor-pointer place-items-center rounded-full border border-dashed border-outline-gray-3 text-ink-gray-6 hover:bg-surface-gray-2 focus-within:ring-2 focus-within:ring-outline-gray-3"
			:title="__('Custom color')"
		>
			<span class="lucide-plus size-3" aria-hidden="true" />
			<input
				type="color"
				:aria-label="__('Custom color')"
				class="absolute inset-0 size-full cursor-pointer opacity-0"
				:value="selected || '#000000'"
				@change="emit('pick', ($event.target as HTMLInputElement).value)"
			/>
		</label>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { SWATCHES, normalizeHex } from "./colorHex";
import { translate as __ } from "../../utils/translate";

const props = defineProps<{ modelValue?: string | null }>();
const emit = defineEmits<{ pick: [hex: string] }>();

const selected = computed(() => normalizeHex(props.modelValue ?? ""));
</script>
