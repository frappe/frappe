<template>
	<div
		class="pfb-insp-row"
		:class="{ 'pfb-insp-row--col': stacked, 'pfb-insp-row--toggle': toggle }"
	>
		<span class="pfb-insp-label">{{ label }}</span>
		<slot />
	</div>
</template>

<script setup>
defineProps({
	label: { type: String, default: "" },
	stacked: { type: Boolean, default: false },
	toggle: { type: Boolean, default: false },
});
</script>
