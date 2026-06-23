<script setup>
defineProps({ size: { type: Number, default: 18 } });
</script>

<template>
	<span
		class="inline-flex shrink-0 items-center justify-center rounded-md bg-surface-gray-7 text-ink-white"
		:style="{ width: `${size}px`, height: `${size}px` }"
	>
		<svg
			:width="size * 0.62"
			:height="size * 0.62"
			viewBox="0 0 24 24"
			fill="currentColor"
			aria-hidden="true"
		>
			<path d="M12 2.5l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.9L12 2.5z" />
			<path
				d="M18.5 14l.95 2.55L22 17.5l-2.55.95L18.5 21l-.95-2.55L15 17.5l2.55-.95L18.5 14z"
			/>
		</svg>
	</span>
</template>
