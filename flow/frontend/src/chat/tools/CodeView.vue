<template>
	<div>
		<CodeBlock :code="code" lang="python" bare />
		<template v-if="returned">
			<div class="border-y border-outline-gray-1 px-3 py-1.5 text-xs text-ink-gray-4">
				{{ __("Result") }}
			</div>
			<ResultView :result="result" />
		</template>
	</div>
</template>

<script setup>
import { computed } from "vue";
import CodeBlock from "@flow/ui-core/components/CodeBlock.vue";
import { __ } from "@flow/ui-core/translate.js";

import ResultView from "./ResultView.vue";

const props = defineProps({
	arguments: { type: Object, required: true },
	result: { type: Object, default: null },
});

const code = computed(() => props.arguments.code ?? "");
const returned = computed(() => !props.result?.is_error && !!props.result?.content);
</script>
