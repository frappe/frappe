<template>
	<!-- Display-only: dev-authored HTML from meta. Sanitized before render. -->
	<!-- eslint-disable-next-line vue/no-v-html -->
	<div class="prose prose-sm max-w-none text-ink-gray-8" v-html="sanitized" />
</template>

<script setup lang="ts">
// Renders the `field.options` HTML in a prose container. Read-only, no emit.
//
// Divergence from core (documented in plans/fieldtypes-remaining.md): core does a
// raw `$wrapper.html()` because it treats this markup as trusted dev metadata. We
// sanitize first — matching CRM's `HtmlControl` — because raw `v-html` is a
// review/XSS flag in a real product. `dompurify` is a transitive dep of the
// `frappe-ui` peer (same as our `reka-ui` usage), so no new direct dependency.
import { computed } from "vue";
import DOMPurify from "dompurify";
import type { FieldComponentProps } from "../types";

const props = defineProps<FieldComponentProps>();

const sanitized = computed(() => DOMPurify.sanitize(props.field.options ?? ""));
</script>
