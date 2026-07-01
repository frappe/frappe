<template>
	<div ref="rootEl" class="activity-timeline">
		<!-- spinner only on first load; cached data stays visible during revalidation -->
		<div v-if="loading && !activities.length" class="flex justify-center py-8">
			<LoadingIndicator class="size-5 text-ink-gray-5" />
		</div>
		<div
			v-else-if="!activities.length"
			class="flex flex-col items-center justify-center gap-3 py-8"
		>
			<LucideActivity class="h-7 w-7 text-ink-gray-4" />
			<span class="text-lg font-medium text-ink-gray-8">No activity yet</span>
		</div>
		<div v-else class="activities flex flex-col gap-2 mt-2" :tabindex="0">
			<!-- LoadMore for Pagination -->
			<div
				v-if="showLoadMoreButton && !loadMoreAtBottom"
				class="mb-1 flex w-full justify-center"
			>
				<LoadMore />
			</div>
			<div
				v-for="(activity, i) in displayActivities"
				:key="getKey(activity, i)"
				:id="getKey(activity, i)"
				class="activity"
			>
				<div class="grid w-full grid-cols-[30px_minmax(auto,_1fr)] gap-2 px-6 md:px-0">
					<!-- gutter column: vertical connector line + icon/avatar -->
					<div
						class="relative flex justify-center after:absolute after:start-[50%] after:z-0 after:border-s after:border-outline-gray-modals"
						:class="
							activity.type === 'load_more'
								? 'after:-top-2 after:h-[calc(100%+1rem)]'
								: [
										i != displayActivities.length - 1 && 'after:h-full',
										isOneLinerActivity(activity)
											? 'after:top-6'
											: 'after:top-3',
								  ]
						"
					>
						<!-- load_more has no gutter icon — the connector line passes straight through -->
						<div
							v-if="activity.type !== 'load_more'"
							class="relative z-10 flex items-center justify-center self-start bg-surface-white"
							:class="[isAvatarActivity(activity) ? 'h-10' : 'h-6 w-6 rounded-full']"
						>
							<!-- gutter ladder: #icon-{type} slot > GutterIcon (activity.icon > per-type default) -->
							<slot :name="`icon-${activity.type}`" :activity="activity">
								<GutterIcon :activity="activity" />
							</slot>
						</div>
					</div>
					<div
						class="mb-4 flex flex-1"
						:class="[i == displayActivities.length - 1 && 'mb-5']"
						:data-type="activity.type"
					>
						<!-- Load More in activity -->
						<div
							v-if="activity.type === 'load_more'"
							class="flex w-full justify-center"
						>
							<LoadMore />
						</div>
						<slot v-else :name="`item-${activity.type}`" :activity="activity">
							<!-- default slot: full per-row override, exposes the row as { item } -->
							<slot :item="activity">
								<EmailItem v-if="activity.type === 'email'" :email="activity" />
								<CommentItem
									v-else-if="activity.type === 'comment'"
									:comment="activity"
								/>
								<LogItem
									v-else-if="
										activity.type === 'log' ||
										activity.type === 'attachment_log'
									"
									:activity="activity"
								/>
								<VersionItem
									v-else-if="activity.type === 'version'"
									:activity="activity"
								/>
							</slot>
						</slot>
					</div>
				</div>
			</div>
			<!-- standalone Load More (bottom): a UI control, not a timeline row -->
			<div
				v-if="showLoadMoreButton && loadMoreAtBottom"
				class="mt-4 flex w-full justify-center"
			>
				<LoadMore />
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { LoadingIndicator } from "frappe-ui";
import { computed, h, ref, useSlots } from "vue";
import CommentItem from "./CommentItem.vue";
import EmailItem from "./EmailItem.vue";
import GutterIcon from "./GutterIcon.vue";
import LoadMoreButton from "./LoadMoreButton.vue";
import LogItem from "./LogItem.vue";
import type { Activity, ActivityTimelineProps, CustomActivity } from "./types";
import { useTimelineScroll } from "./useTimelineScroll";
import VersionItem from "./VersionItem.vue";

const props = withDefaults(defineProps<ActivityTimelineProps>(), {
	loading: false,
});

defineSlots<
	// known activity types
	{ [K in Activity as `item-${K["type"]}`]?: (props: { activity: K }) => any } & {
		[K in Activity as `icon-${K["type"]}`]?: (props: { activity: K }) => any;
	} & {
		// custom activity types
		[name: `item-${string}`]: (props: { activity: Activity | CustomActivity }) => any;
		[name: `icon-${string}`]: (props: { activity: Activity | CustomActivity }) => any;
		default?: (props: { item: Activity | CustomActivity }) => any;
		// override the default "Load more" control
		load_more?: (props: { loading: boolean; loadMore: () => void }) => any;
	}
>();

const rootEl = ref<HTMLElement | null>(null);
const slots = useSlots();

const isFetching = computed(() => !!props.paginate?.isFetchingNextPage);

// "inline" injects a load_more row above the oldest email; top/bottom show a standalone button.
const isInline = computed(() => props.paginate?.loadMore?.position === "inline");
const showLoadMoreButton = computed(() => !!props.paginate?.hasNextPage && !isInline.value);

// Rows to render: the raw feed, plus an in-feed load_more row above the oldest email when paginating inline.
const displayActivities = computed<Array<Activity | CustomActivity>>(() => {
	const list = props.activities;
	if (!isInline.value || !props.paginate?.hasNextPage) return list;
	const idx = list.findIndex((a) => a.type === "email");
	if (idx === -1) return list;
	const loadMore: CustomActivity = {
		type: "load_more",
		key: "load-more",
		timestamp: list[idx].timestamp,
		data: null,
	};
	return [...list.slice(0, idx), loadMore, ...list.slice(idx)];
});

// can be rendered at up to three sites (top / in-feed row / bottom) that differ only in wrapper.
const LoadMore = () =>
	slots.load_more
		? slots.load_more({ loading: isFetching.value, loadMore })
		: h(LoadMoreButton, {
				loading: isFetching.value,
				onClick: loadMore,
				label: props.paginate?.loadMore?.label,
				icon: props.paginate?.loadMore?.icon,
		  });

const loadMoreAtBottom = computed(() => props.paginate?.loadMore?.position === "bottom");
// Which row to re-pin after older rows patch in, so the viewport doesn't move.

// scroll-to-bottom + anchor restore on Load More live in the composable
const { captureAnchor } = useTimelineScroll(
	rootEl,
	computed(() => displayActivities.value.length),
	() => !!props.paginate
);

function loadMore() {
	captureAnchor(anchorRowKey());
	props.paginate?.fetchNextPage();
}
function anchorRowKey(): string | null {
	const list = displayActivities.value;
	// in-feed load_more: pin the row just below it
	const idx = list.findIndex((a) => a.type === "load_more");
	if (idx !== -1) return list[idx + 1] ? getKey(list[idx + 1], idx + 1) : null;
	// standalone button: bottom appends (no re-pin); top prepends, so pin the first row
	if (loadMoreAtBottom.value) return null;
	return list[0] ? getKey(list[0], 0) : null;
}

// Stable v-for key / scroll-target id; custom rows may omit `key`.
function getKey(activity: Activity | CustomActivity, index: number): string {
	return (
		activity.key ??
		(activity.timestamp
			? `${activity.type}:${activity.timestamp}`
			: `${activity.type}:${index}`)
	);
}

// email + comment show the author avatar on the axis instead of a gutter icon
function isAvatarActivity(activity: Activity): boolean {
	return activity.type === "email" || activity.type === "comment";
}

// one-line rows (log/attachment/version) nudge the icon to center on the single line
function isOneLinerActivity(activity: Activity): boolean {
	return (
		activity.type === "log" ||
		activity.type === "attachment_log" ||
		activity.type === "version"
	);
}
</script>
