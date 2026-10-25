<template>
	<div class="prose prose-sm max-w-none" v-html="safe" />
</template>

<script setup lang="ts">
// Stored rich text drawn without the editor, so it costs none of the editor's chunk.
import { computed } from "vue";
import { sanitizeHtml } from "../../utils/sanitize";

const props = defineProps<{ html: string | null | undefined }>();

const safe = computed(() => sanitizeHtml(props.html));
</script>
