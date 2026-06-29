<template>
	<!-- default Load More affordance; override via the timeline's #load_more slot -->
	<Button :loading="loading" icon-left="lucide-refresh-cw"> Load More Emails </Button>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";

defineProps<{
	/** the next page is in flight — show the spinner */
	loading?: boolean;
}>();

// click falls through to the root <Button>; the timeline binds @click="loadMore()"
</script>
