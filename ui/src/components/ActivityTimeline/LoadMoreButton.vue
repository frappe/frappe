<template>
	<!-- default Load More control; override via the timeline's #load_more slot -->
	<Button :loading="loading" icon-left="lucide-refresh-cw"> Load more </Button>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";

defineProps<{ loading?: boolean }>();
// click falls through to the root <Button>; the timeline binds @click="loadMore"
</script>
