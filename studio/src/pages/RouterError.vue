<template>
	<div class="flex h-screen w-full items-center justify-center bg-surface-gray-1 p-4">
		<div class="flex max-w-lg flex-col items-center text-center">
			<h1 class="text-xl font-semibold text-ink-gray-7">This app's router failed to start</h1>
			<pre class="mt-3 whitespace-pre-wrap break-words font-mono text-sm text-ink-red-6">{{ message }}</pre>
			<div class="mt-3 text-base text-ink-gray-5">
				Fix the router script and reload. Details are in the console.
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
defineProps<{ message: string }>()
</script>
