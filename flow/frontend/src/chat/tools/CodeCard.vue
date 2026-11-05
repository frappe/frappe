<template>
	<div class="px-3.5 py-2">
		<button type="button" class="text-base text-ink-gray-7 hover:underline" @click="open = !open">
			{{ open ? "Hide code" : "Show code" }}
		</button>
	</div>
	<CodeBlock v-if="open" :code="code" lang="python" bare />
</template>

<script setup>
import { computed, ref } from "vue";
import CodeBlock from "@flow/ui-core/components/CodeBlock.vue";

// execute's approval card: the title already says what the code does, so the code waits behind a button
const props = defineProps({ arguments: { type: Object, required: true } });
const code = computed(() => props.arguments.code ?? "");
const open = ref(false);
</script>
