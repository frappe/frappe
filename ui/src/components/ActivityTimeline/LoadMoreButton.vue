<template>
	<!-- default Load More control; override via the timeline's #load_more slot -->
	<Button :loading="loading" :icon-left="buttonInfo.icon">
		{{ buttonInfo.label }}
	</Button>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { computed } from "vue";

const props = defineProps<{ loading?: boolean; isDefaultTimeline?: boolean }>();

const buttonInfo = computed(() => ({
	icon: props.isDefaultTimeline ? "lucide-chevrons-up" : "lucide-refresh-cw",
	label: props.isDefaultTimeline ? "Show previous conversations" : "Load more",
}));

// click falls through to the root <Button>; the timeline binds @click="loadMore"
</script>
