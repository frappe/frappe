<script setup>
import { __ } from "@/lib/translate";
defineProps({ label: { type: String, default: "" } });
</script>

<template>
	<div class="flex items-center gap-2 text-ink-gray-5">
		<span class="flow-dots"> <span></span><span></span><span></span> </span>
		<span v-if="label" class="flow-shimmer text-sm">{{ label }}</span>
	</div>
</template>

<style scoped>
.flow-dots {
	display: inline-flex;
	gap: 3px;
}
.flow-dots span {
	width: 5px;
	height: 5px;
	border-radius: 50%;
	background: currentColor;
	animation: flow-bounce 1.4s infinite ease-in-out both;
}
.flow-dots span:nth-child(1) {
	animation-delay: -0.32s;
}
.flow-dots span:nth-child(2) {
	animation-delay: -0.16s;
}
@keyframes flow-bounce {
	0%,
	80%,
	100% {
		transform: scale(0);
		opacity: 0.4;
	}
	40% {
		transform: scale(1);
		opacity: 1;
	}
}
.flow-shimmer {
	background: linear-gradient(
		90deg,
		var(--ink-gray-5) 25%,
		var(--ink-gray-8) 50%,
		var(--ink-gray-5) 75%
	);
	background-size: 200% 100%;
	-webkit-background-clip: text;
	background-clip: text;
	-webkit-text-fill-color: transparent;
	animation: flow-shimmer 1.6s linear infinite;
}
@keyframes flow-shimmer {
	0% {
		background-position: 200% 0;
	}
	100% {
		background-position: -200% 0;
	}
}
</style>
