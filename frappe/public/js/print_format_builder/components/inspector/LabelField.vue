<template>
	<div class="pfb-insp-row pfb-insp-row--col">
		<span class="pfb-insp-label">{{ label }}</span>
		<div class="label-field-controls">
			<label v-if="showToggle" class="switch-control" :title="showLabel">
				<span class="input-area">
					<input
						type="checkbox"
						role="switch"
						:aria-label="showLabel"
						:checked="show_on"
						@change="$emit('update:show', $event.target.checked ? 'show' : 'hide')"
					/>
				</span>
				<span class="switch-visual" aria-hidden="true">
					<span class="switch-thumb"></span>
				</span>
			</label>
			<input
				v-if="!showToggle || show_on"
				class="pfb-insp-input"
				type="text"
				:placeholder="placeholder"
				:value="modelValue"
				@input="$emit('update:modelValue', $event.target.value)"
			/>
		</div>
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

<style scoped>
.label-field-controls {
	display: flex;
	align-items: center;
	gap: 10px;
}

.label-field-controls .pfb-insp-input {
	flex: 1;
}
</style>
