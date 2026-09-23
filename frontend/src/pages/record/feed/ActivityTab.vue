<!-- The Activity tab: every type, or the types a script chose, with the script's own rows. -->
<template>
	<TimelineFeed :key="typesKey" :page="page" :types="types" main />
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import type { RecordPageApi } from "@/recordPage";
import { RecordFeedsKey } from "./recordFeeds";
import TimelineFeed from "./TimelineFeed.vue";

defineProps<{ page: RecordPageApi }>();

const feeds = inject(RecordFeedsKey, null);

// The read is bound to its types, so a new list draws a new feed.
const types = computed(() => feeds?.controller()?.activity.shownTypes() ?? undefined);
const typesKey = computed(() => JSON.stringify(types.value ?? "*"));
</script>
