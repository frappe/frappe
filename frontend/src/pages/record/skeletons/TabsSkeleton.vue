<!-- The tab strip and the body the address opens, the feed or the Details form, before the
     page's first replay, each in its real padding and column, so the real ones land in place. -->
<template>
	<div class="flex min-h-0 flex-1 flex-col">
		<div
			class="shrink-0 border-b border-outline-gray-1 px-[--page-gutter] py-2"
			data-record-tabs-skeleton
		>
			<div class="flex h-7 items-center gap-5">
				<Skeleton v-for="n in 4" :key="n" class="h-4 w-16 rounded-4" />
			</div>
		</div>
		<!-- The strip has no status of its own: the feed's or the form's skeleton carries it. -->
		<div v-if="feed" class="min-h-0 flex-1 overflow-hidden px-6 pb-8 pt-4" data-feed-skeleton>
			<div class="mx-auto flex w-full max-w-3xl flex-col gap-5">
				<TimelineSkeleton class="mt-2" :label="__('Loading')" />
			</div>
		</div>
		<FormSkeleton
			v-else
			:columns="2"
			:fields="8"
			class="mx-auto w-full max-w-3xl px-[--page-gutter] py-6"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { Skeleton } from "frappe-ui";
import { TimelineSkeleton } from "@framework/ui/ActivityTimeline";
import { __ } from "@/i18n";
import { addressesFeed } from "../feed/recordFeeds";
import FormSkeleton from "./FormSkeleton.vue";

const route = useRoute();
// Scripts may still put Activity first on a plain address; that order is known only after the replay.
const feed = computed(() => addressesFeed(route.query));
</script>
