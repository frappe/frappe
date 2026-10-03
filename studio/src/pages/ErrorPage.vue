<template>
	<div class="flex h-screen w-full items-center justify-center bg-surface-gray-1 p-4">
		<div class="flex w-full max-w-2xl flex-col items-center text-center">
			<h1 class="text-xl font-semibold text-ink-gray-7">Something went wrong</h1>
			<div class="mt-2 text-base text-ink-gray-5">This app could not start. Please try again later.</div>
			<template v-if="error">
				<Button
					class="mt-4"
					size="sm"
					:label="showError ? 'Hide Error' : 'Show Error'"
					@click="showError = !showError"
				/>
				<pre
					v-if="showError"
					class="mt-3 max-h-96 w-full overflow-auto rounded-6 bg-surface-gray-2 p-3 text-left font-mono text-xs leading-5"
				><code><span class="font-semibold text-ink-red-6">{{ title }}</span><template v-for="frame in frames" :key="frame.text">
<span class="text-ink-gray-5">    at </span><span class="text-ink-gray-8">{{ frame.name }}</span><span class="text-ink-blue-5">{{ frame.location }}</span></template></code></pre>
			</template>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button } from "frappe-ui"

const props = defineProps<{ error?: string | null }>()

const showError = ref(false)
const lines = computed(() => (props.error || "").split("\n"))
const title = computed(() => lines.value.filter((line) => !isFrame(line)).join("\n"))
const frames = computed(() => lines.value.filter(isFrame).map(parseFrame))

function isFrame(line: string) {
	return /^\s+at /.test(line)
}

// `at fn (file:line:col)` or `at file:line:col`
function parseFrame(line: string) {
	const text = line.trim().slice(3)
	const match = text.match(/^(.*?) \((.*)\)$/)
	return match
		? { text, name: `${match[1]} `, location: `(${match[2]})` }
		: { text, name: "", location: text }
}
</script>
