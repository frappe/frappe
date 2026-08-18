<template>
	<!-- default Load More control; override via the timeline's #load_more slot -->
	<Button :loading="loading" :icon-left="icon ?? 'lucide-refresh-cw'">
		{{ label ?? "Load more" }}
	</Button>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import type { Component } from "vue";

// icon accepts a lucide-* string or a component — Button's :icon-left resolves both.
defineProps<{ loading?: boolean; label?: string; icon?: string | Component }>();

// click falls through to the root <Button>; the timeline binds @click="loadMore"
</script>
