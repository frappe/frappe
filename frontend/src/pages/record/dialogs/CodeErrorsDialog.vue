<!-- The body of the dialog a save opens when a Code field's text does not compile. -->
<template>
	<div class="space-y-4">
		<section v-for="(frame, i) in frames" :key="i" class="space-y-1.5" data-code-error>
			<p class="text-p-sm-medium text-ink-gray-8">
				{{ __("{0}, line {1}, column {2}", [frame.label, frame.line, frame.column]) }}
			</p>
			<p class="text-p-sm text-ink-red-4">{{ frame.message }}</p>
			<pre
				class="overflow-x-auto rounded-5 bg-surface-gray-2 py-2 font-mono text-p-xs text-ink-gray-7"
			><template v-for="row in frame.lines" :key="row.number"><div
				class="px-3"
				:class="{ 'bg-surface-red-2 text-ink-gray-9': row.number === frame.line }"
			><span class="mr-3 inline-block w-6 select-none text-right text-ink-gray-4">{{ row.number }}</span>{{ row.text }}</div><div
				v-if="row.number === frame.line"
				class="px-3 text-ink-red-4"
			><span class="mr-3 inline-block w-6 select-none" />{{ frame.indent }}^</div></template></pre>
		</section>
	</div>
</template>

<script setup lang="ts">
import { __ } from "@/i18n";
import type { CodeErrorFrame } from "../codeErrorFrames";

defineProps<{ frames: CodeErrorFrame[]; close: (value?: any) => void }>();
</script>
