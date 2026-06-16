<script setup>
defineProps({ content: { type: String, default: "" } });
</script>

<template>
	<div class="flex justify-end">
		<div
			class="max-w-[88%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-surface-gray-2 px-3.5 py-2.5 text-[length:var(--text-base)] font-normal leading-relaxed text-ink-gray-9"
		>
			{{ content }}
		</div>
	</div>
</template>
