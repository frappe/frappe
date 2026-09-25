<template>
	<!-- Display-only: dev-authored HTML from meta, sanitized before render. -->
	<!-- eslint-disable-next-line vue/no-v-html -->
	<div class="prose prose-sm max-w-none text-ink-gray-8" v-html="sanitized" />
</template>

<script setup lang="ts">
// Read-only render of `field.options` HTML. We sanitize first (core uses raw
// `$wrapper.html()`) to avoid an XSS flag; `dompurify` is a transitive `frappe-ui` dep.
import { computed } from "vue";
import DOMPurify from "dompurify";
import type { FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();

const sanitized = computed(() => DOMPurify.sanitize(props.field.options ?? ""));
</script>
