<!--
  The tile grid while its tiles load: the same columns and gap, each bar one tile tall.
-->
<template>
	<div class="grid max-w-2xl grid-cols-2 gap-2" data-tile-skeleton>
		<LoadingStatus />
		<Skeleton v-for="tile in 6" :key="tile" class="h-9 rounded-4" />
	</div>
</template>

<script setup lang="ts">
import { Skeleton } from "frappe-ui";
import LoadingStatus from "@/shell/LoadingStatus.vue";
</script>
