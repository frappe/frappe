<!-- The Document Status column: Draft, Submitted or Cancelled, coloured as desk v1 does. -->
<template>
	<Badge :label="shown.label" :theme="shown.theme" />
</template>

<script setup lang="ts">
import { Badge } from "frappe-ui";
import type { BadgeProps } from "frappe-ui";
import { computed } from "vue";
import { __ } from "@/i18n";

const props = defineProps<{ value: unknown }>();

const STATUSES: Record<number, { label: string; theme: BadgeProps["theme"] }> = {
	0: { label: __("Draft"), theme: "red" },
	1: { label: __("Submitted"), theme: "blue" },
	2: { label: __("Cancelled"), theme: "red" },
};

const shown = computed(() => STATUSES[Number(props.value)] ?? STATUSES[0]);
</script>
