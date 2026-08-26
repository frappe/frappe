<template>
	<div class="pfb-insp-row pfb-insp-row--toggle">
		<span class="pfb-insp-label">{{ label }}</span>
		<label class="switch-control" :title="label">
			<span class="input-area">
				<input
					type="checkbox"
					role="switch"
					:aria-label="label"
					:checked="modelValue"
					@change="$emit('update:modelValue', $event.target.checked)"
				/>
			</span>
			<span class="switch-visual" aria-hidden="true">
				<span class="switch-thumb"></span>
			</span>
		</label>
	</div>
</template>

<script setup>
defineProps({
	label: { type: String, default: "" },
	modelValue: { type: Boolean, default: false },
});
defineEmits(["update:modelValue"]);
</script>
