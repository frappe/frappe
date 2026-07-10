<template>
	<div class="pfb-insp-row" v-if="showToggle">
		<span class="pfb-insp-label">{{ showLabel }}</span>
		<label class="switch-control">
			<span class="input-area">
				<input
					type="checkbox"
					role="switch"
					:checked="show_on"
					@change="$emit('update:show', $event.target.checked ? 'show' : 'hide')"
				/>
			</span>
			<span class="switch-visual" aria-hidden="true">
				<span class="switch-thumb"></span>
			</span>
		</label>
	</div>
	<div class="pfb-insp-row pfb-insp-row--col" v-if="!showToggle || show_on">
		<span class="pfb-insp-label">{{ label }}</span>
		<input
			class="pfb-insp-input"
			type="text"
			:placeholder="placeholder"
			:value="modelValue"
			@input="$emit('update:modelValue', $event.target.value)"
		/>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	modelValue: { type: String, default: "" },
	label: { type: String, default: () => __("Label") },
	placeholder: { type: String, default: "" },
	show: { type: String, default: undefined },
	showToggle: { type: Boolean, default: false },
	showLabel: { type: String, default: () => __("Show label") },
});
defineEmits(["update:modelValue", "update:show"]);

let show_on = computed(() => props.show !== "hide");
</script>
