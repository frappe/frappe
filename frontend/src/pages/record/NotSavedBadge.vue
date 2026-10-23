<!-- The new record's mark in the header row until its first save. -->
<template>
	<Badge :label="__('Not Saved')" theme="amber" />
</template>

<script setup lang="ts">
import { Badge } from "frappe-ui";
import { __ } from "@/i18n";

defineProps<{ page?: unknown }>();
</script>
