<!-- The record's status in the header row, beside its title. -->
<template>
	<Badge :label="label" :theme="theme" />
</template>

<script setup lang="ts">
import { Badge } from "frappe-ui";
import type { BadgeProps } from "frappe-ui";

defineProps<{ label: string; theme?: BadgeProps["theme"]; page?: unknown }>();
</script>
