<!-- One activity read, oldest first, opening at the newest row. The Activity tab's own feed
     also draws a script's rows in time order and answers `page.activity`. -->
<template>
	<RecordFeed
		:paginate="paginate"
		:error="error"
		:ready="activities.length > 0 || !loading"
		openAtBottom
	>
		<!-- The feed is the one scroller and the one tab stop. -->
		<ActivityTimeline
			ref="timeline"
			:scrolls="false"
			:activities="rows"
			:loading="loading"
			:paginate="paginate"
		>
			<!-- The feed pages on scroll, so the timeline's own button stays out. -->
			<template #load_more />
			<template v-if="empty" #empty>
				<div class="flex flex-col items-center justify-center gap-3 py-8">
					<span class="size-7 text-ink-gray-4" :class="empty.icon" aria-hidden="true" />
					<span class="text-md font-medium text-ink-gray-8">{{ empty.label }}</span>
				</div>
			</template>
			<template v-if="canReply" #item-email="{ activity }">
				<EmailItem :email="activity">
					<template v-if="!activity.pending" #actions>
						<Button
							icon="lucide-reply"
							variant="ghost"
							:label="__('Reply')"
							:tooltip="__('Reply')"
							data-email-reply
							@click="reply(activity.key)"
						/>
						<Button
							icon="lucide-reply-all"
							variant="ghost"
							:label="__('Reply all')"
							:tooltip="__('Reply all')"
							data-email-reply-all
							@click="reply(activity.key, true)"
						/>
					</template>
				</EmailItem>
			</template>
			<template #item-script="{ activity }">
				<component
					:is="scriptItem(activity).component"
					v-bind="{ ...scriptItem(activity).props, page }"
				/>
			</template>
		</ActivityTimeline>
	</RecordFeed>
</template>

<script setup lang="ts">
import { computed, inject, onUnmounted, ref } from "vue";
import { Button } from "frappe-ui";
import {
	ActivityTimeline,
	compareActivities,
	EmailItem,
	useActivityTimeline,
	type CustomActivity,
	type VisibleTypes,
} from "@framework/ui/ActivityTimeline";
import type { ActivityRow, FeedItem, RecordPageApi } from "@/recordPage";
import { __ } from "@/i18n";
import { EMAIL_WRITER } from "../composer/emailDraft";
import RecordFeed from "./RecordFeed.vue";
import { RecordFeedsKey } from "./recordFeeds";

defineOptions({ scrollsItself: true });

const props = defineProps<{
	page: RecordPageApi;
	types?: VisibleTypes;
	/** The Activity tab's feed: script rows join it, and the host reads it. */
	main?: boolean;
	/** What an empty feed says, in place of the timeline's own words. */
	empty?: { icon: string; label: string };
}>();

const feeds = inject(RecordFeedsKey)!;
const timeline = ref<InstanceType<typeof ActivityTimeline> | null>(null);
const { activities, loading, error, reload, paginate } = useActivityTimeline(
	props.page.doctype,
	props.page.docname,
	props.types
);
const loaded = computed(() => activities.value as ActivityRow[]);

const rows = computed(() => (props.main ? withScriptRows(loaded.value) : loaded.value));

// The email writer is listed only with the email right, so its presence is the gate.
const canReply = computed(() => {
	const writers = feeds.controller()?.composer.visible() ?? [];
	return writers.some((writer) => writer.name === EMAIL_WRITER);
});

if (props.main) {
	const release = feeds.attach({
		activities: loaded,
		loading,
		error,
		paginate,
		reload,
		scrollToRow: (key) => timeline.value?.scrollToRow(key) ?? false,
	});
	onUnmounted(release);
}

function withScriptRows(server: ActivityRow[]): Array<ActivityRow | CustomActivity> {
	const taken = new Set(server.map((row) => row.key));
	const own = (feeds.controller()?.activity.visible() ?? [])
		.filter((item) => !taken.has(item.name))
		.map((item) => ({
			type: "script",
			key: item.name,
			timestamp: item.timestamp,
			data: item,
		}));
	return own.length ? [...server, ...own].sort(compareActivities) : server;
}

function reply(key: string, all = false) {
	const draft = all ? { replyTo: key, replyAll: true } : { replyTo: key };
	props.page.composer.open(EMAIL_WRITER, { draft });
}

function scriptItem(activity: { data: unknown }) {
	return activity.data as FeedItem;
}
</script>
