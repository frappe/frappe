<template>
	<img
		:src="otto"
		:width="size"
		:height="size"
		alt="Flow"
		class="block flex-none select-none object-contain"
		:style="{ width: `${size}px`, height: `${size}px` }"
	/>
</template>

<script setup>
import otto from "../assets/flow.png"

defineProps({ size: { type: Number, default: 18 } })
</script>
