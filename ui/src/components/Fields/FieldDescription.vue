<!-- A DocType field's description, drawn as HTML like desk v1 draws it (`<br>`, `<code>`, links). -->
<template>
	<span
		class="[&_a]:underline [&_b]:font-semibold [&_code]:rounded-2 [&_code]:bg-surface-gray-2 [&_code]:px-1 [&_code]:font-mono [&_ol]:list-decimal [&_ol]:ps-4 [&_pre]:whitespace-pre-wrap [&_ul]:list-disc [&_ul]:ps-4"
		v-html="safe"
	/>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { descriptionHtml } from "./fieldDescription";

const props = defineProps<{ html?: string }>();

const safe = computed(() => descriptionHtml(props.html));
</script>
