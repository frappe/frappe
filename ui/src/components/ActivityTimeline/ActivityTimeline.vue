<template>
	<!-- column-reverse scroller: opens pinned to the newest row natively; needs a bounded height -->
	<div ref="rootEl" class="activity-timeline flex flex-col-reverse overflow-y-auto">
		<!-- min-h-full keeps short feeds at the top; shrink-0 keeps the overflow -->
		<div class="min-h-full shrink-0">
			<!-- spinner only on first load; cached data stays visible during revalidation -->
			<div v-if="loading && !activities.length" class="flex justify-center py-8">
				<LoadingIndicator class="size-5 text-ink-gray-5" />
			</div>
			<template v-else-if="!activities.length">
				<slot name="empty">
					<div class="flex flex-col items-center justify-center gap-3 py-8">
						<LucideActivity class="h-7 w-7 text-ink-gray-4" />
						<span class="text-md font-medium text-ink-gray-8">No activity yet</span>
					</div>
				</slot>
			</template>
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
					<!-- minmax 0: lets the content column shrink so inner truncation can engage -->
					<div class="grid w-full grid-cols-[30px_minmax(0,_1fr)] gap-2 px-6 md:px-0">
						<!-- gutter column: vertical connector line + icon/avatar -->
						<div
							class="relative flex justify-center after:absolute after:start-[50%] after:z-0 after:border-s after:border-outline-elevation-2"
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
								class="relative z-10 flex items-center justify-center self-start bg-surface-base"
								:class="[
									isAvatarActivity(activity) ? 'h-10' : 'h-6 w-6 rounded-full',
								]"
							>
								<!-- gutter ladder: #icon-{type} slot > DotIcon (activity.icon > per-type default) -->
								<slot :name="`icon-${activity.type}`" :activity="activity">
									<DotIcon :activity="activity" />
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
									<EmailItem
										v-if="activity.type === 'email'"
										:email="activity"
									/>
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
	</div>
</template>

<script setup lang="ts">
import { LoadingIndicator } from "frappe-ui";
import { computed, h, ref, useSlots } from "vue";
import CommentItem from "./CommentItem.vue";
import EmailItem from "./EmailItem.vue";
import DotIcon from "./DotIcon.vue";
import { groupActivities } from "./grouping";
import LoadMoreButton from "./LoadMoreButton.vue";
import LogItem from "./LogItem.vue";
import type { Activity, ActivityTimelineProps, CustomActivity } from "./types";
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
		// replaces the built-in "No activity yet" state
		empty?: () => any;
		// override the default "Load more" control
		load_more?: (props: { loading: boolean; loadMore: () => void }) => any;
	}
>();

const rootEl = ref<HTMLElement | null>(null);
const slots = useSlots();

const isFetching = computed(() => !!props.paginate?.isFetchingNextPage);

// "inline" injects a load_more row above the oldest paged row; top/bottom show a standalone button.
const isInline = computed(() => props.paginate?.loadMore?.position === "inline");
const showLoadMoreButton = computed(() => !!props.paginate?.hasNextPage && !isInline.value);

// Which rows the next page extends. Emails by default, so a paginate without one behaves as before.
const isPagedRow = computed(
	() => props.paginate?.isPagedRow ?? ((a: Activity | CustomActivity) => a.type === "email")
);

// Rows to render: the feed, plus an in-feed load_more row above the oldest paged row.
const displayActivities = computed<Array<Activity | CustomActivity>>(() => {
	// grouped here, over the final rendered feed — a visible row between two saves
	// splits the fold, so summaries never reorder against comments/calls
	const list = groupActivities(props.activities as Activity[]);
	if (!isInline.value || !props.paginate?.hasNextPage) return list;
	const idx = list.findIndex(isPagedRow.value);
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

function loadMore() {
	props.paginate?.fetchNextPage();
}

// column-reverse: scrollTop 0 is the newest row; unbounded, the scrolling ancestor jumps instead
function scrollToLatest() {
	const el = rootEl.value;
	if (!el) return;
	if (el.scrollHeight > el.clientHeight) el.scrollTop = 0;
	else el.scrollIntoView({ block: "end" });
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

// Deep-link affordance: scroll a row (by its key/id) into view and flash it.
function scrollToRow(key: string): boolean {
	const row = rootEl.value?.querySelector<HTMLElement>(`[id="${CSS.escape(key)}"]`);
	if (!row) return false;
	row.scrollIntoView({ block: "center" });
	row.classList.remove("timeline-row-flash");
	// restart the animation if the row was already flashing
	void row.offsetWidth;
	row.classList.add("timeline-row-flash");
	row.addEventListener("animationend", () => row.classList.remove("timeline-row-flash"), {
		once: true,
	});
	return true;
}

defineExpose({ scrollToRow, scrollToLatest });

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

<style scoped>
/* row roots (slot content included) must shrink so inner truncation can engage */
[data-type] > :deep(*) {
	min-width: 0;
}

/* card rows flash the card ring below instead of a row background */
.timeline-row-flash:not(:has(.timeline-card)) {
	animation: timeline-row-flash 2s ease-out;
	border-radius: 0.5rem;
}
@keyframes timeline-row-flash {
	0%,
	40% {
		background-color: var(--surface-gray-2);
	}
	100% {
		background-color: transparent;
	}
}

/* card rows paint their own background over the row, so ring the card instead */
.timeline-row-flash :deep(.timeline-card) {
	animation: timeline-card-flash 2s ease-out;
}
@keyframes timeline-card-flash {
	0%,
	40% {
		box-shadow: 0 0 0 2px var(--outline-gray-3);
	}
	100% {
		box-shadow: 0 0 0 2px transparent;
	}
}
</style>
