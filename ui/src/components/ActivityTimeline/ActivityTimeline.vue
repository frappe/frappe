<template>
	<div ref="rootEl" class="activity-timeline">
		<!-- spinner only on first load; cached data stays visible during revalidation -->
		<div v-if="loading && !activities.length" class="flex justify-center py-8">
			<LoadingIndicator class="size-5 text-ink-gray-5" />
		</div>
		<ErrorMessage v-else-if="error" :message="error" class="py-4" />
		<div
			v-else-if="!activities.length"
			class="flex flex-col items-center justify-center gap-3 py-8"
		>
			<FeatherIcon name="activity" class="h-7 w-7 text-ink-gray-4" />
			<span class="text-lg font-medium text-ink-gray-8">No activity found</span>
		</div>
		<div v-else class="activities mt-0.5">
			<div
				v-for="(activity, i) in rows"
				:key="getKey(activity, i)"
				:id="getKey(activity, i)"
				class="activity mt-2"
				:tabindex="0"
			>
				<div class="grid w-full grid-cols-[30px_minmax(auto,_1fr)] gap-2 px-6 md:px-0">
					<!-- gutter column: vertical connector line + icon/avatar -->
					<div
						class="relative flex justify-center after:absolute after:start-[50%] after:-z-10 after:border-s after:border-outline-gray-modals"
						:class="
							activity.type === 'load_more'
								? 'after:-top-2 after:h-[calc(100%+1rem)]'
								: [
										i != rows.length - 1 && 'after:h-full',
										isOneLinerActivity(activity)
											? 'after:top-6'
											: 'after:top-3',
								  ]
						"
					>
						<!-- load_more has no gutter icon — the connector line passes straight through -->
						<div
							v-if="activity.type !== 'load_more'"
							class="z-1 flex items-center justify-center self-start bg-surface-white"
							:class="[isAvatarActivity(activity) ? 'h-10' : 'h-6 w-6 rounded-full']"
						>
							<!-- gutter ladder: #icon-{type} slot > activity.icon > per-type default -->
							<slot :name="`icon-${activity.type}`" :activity="activity">
								<component
									v-if="activity.icon && typeof activity.icon !== 'string'"
									:is="activity.icon"
									class="size-4 text-ink-gray-5"
								/>
								<span
									v-else-if="typeof activity.icon === 'string'"
									:class="[
										LUCIDE_ICON_CLASS[activity.icon],
										'size-4 text-ink-gray-5',
									]"
								/>
								<template v-else>
									<!-- avatar on the axis + channel badge (mail/comment) -->
									<div v-if="isAvatarActivity(activity)" class="relative">
										<Avatar
											size="lg"
											:label="activity.author.fullname"
											:image="activity.author.image"
										/>
										<span
											class="absolute -bottom-0.5 -end-1.5 flex size-4.5 items-center justify-center rounded-full bg-surface-white text-ink-gray-5"
										>
											<MailIcon
												v-if="activity.type === 'email'"
												class="size-3"
											/>
											<CommentIcon v-else class="size-3" />
										</span>
									</div>
									<template
										v-else-if="
											activity.type === 'log' ||
											activity.type === 'attachment_log' ||
											activity.type === 'version'
										"
									>
										<DotIcon
											v-if="
												activity.type === 'version' ||
												(activity.type === 'log' &&
													(activity.data.subtype === 'assigned' ||
														activity.data.subtype ===
															'assignment_completed' ||
														activity.data.subtype === 'created'))
											"
											class="text-ink-gray-5"
										/>
										<span
											v-else
											:class="[
												gutterIconClass(activity),
												'size-4 text-ink-gray-5',
											]"
										/>
									</template>
									<CommentIcon
										v-else
										class="absolute start-[7.5px] text-ink-gray-5"
									/>
								</template>
							</slot>
						</div>
					</div>
					<div
						class="mb-4 flex flex-1"
						:class="[i == rows.length - 1 && 'mb-5']"
						:data-type="activity.type"
					>
						<!-- in-feed Load More: fetches older communications; viewport stays put -->
						<div
							v-if="activity.type === 'load_more'"
							class="flex w-full justify-center"
						>
							<Button
								:loading="!!paginate?.isFetchingNextPage"
								icon-left="lucide-refresh-cw"
								@click="loadMore()"
							>
								Load More Emails
							</Button>
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
		</div>
	</div>
</template>

<script setup lang="ts">
import { Avatar, Button, ErrorMessage, FeatherIcon, LoadingIndicator } from "frappe-ui";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import MailIcon from "~icons/lucide/mail";
import CommentItem from "./CommentItem.vue";
import EmailItem from "./EmailItem.vue";
import { CommentIcon, DotIcon, LUCIDE_ICON_CLASS } from "./icons";
import LogItem from "./LogItem.vue";
import type {
	Activity,
	ActivityTimelineProps,
	AttachmentLogActivity,
	CustomActivity,
	LogActivity,
} from "./types";
import { useScrollContainer } from "./useScrollContainer";
import VersionItem from "./VersionItem.vue";

const props = withDefaults(defineProps<ActivityTimelineProps>(), {
	loading: false,
	error: null,
});

const rootEl = ref<HTMLElement | null>(null);
const { scrollEl } = useScrollContainer(rootEl);

// Virtual "Load More" row (rendered as a button). If the list already carries one, the
// placer owns its position; otherwise auto-place from paginate.position ('top' default).
const rows = computed<Array<Activity | CustomActivity>>(() => {
	const list = props.activities;
	if (list.some((a) => a.type === "load_more")) return list;
	if (!props.paginate?.hasNextPage) return list;

	const atBottom = props.paginate.position === "bottom";
	const loadMore: CustomActivity = {
		type: "load_more",
		key: "load-more",
		timestamp: (atBottom ? list.at(-1) : list[0])?.timestamp,
		data: null,
	};
	return atBottom ? [...list, loadMore] : [loadMore, ...list];
});

// Anchor: the row just below the load_more button + its offset; re-pinning it after the
// fetch keeps the view fixed. Null when the button is at the bottom (re-pin no-ops then).
let anchorKey: string | null = null;
let anchorOffset = 0;

function anchorRowKey(): string | null {
	const list = rows.value;
	const idx = list.findIndex((a) => a.type === "load_more");
	if (idx === -1) return null;
	const next = list[idx + 1];
	return next ? getKey(next, idx + 1) : null;
}

function loadMore() {
	const el = scrollEl.value;
	const key = anchorRowKey();
	const row =
		el && key ? rootEl.value?.querySelector<HTMLElement>(`[id="${CSS.escape(key)}"]`) : null;
	if (el && row && key) {
		anchorKey = key;
		anchorOffset = row.getBoundingClientRect().top - el.getBoundingClientRect().top;
	}
	props.paginate?.fetchNextPage();
}

if (props.paginate) {
	// re-pin the anchor after older rows patch in, so the viewport doesn't move
	watch(
		() => props.activities.length,
		() => {
			const el = scrollEl.value;
			if (!el || anchorKey == null) return;
			const key = anchorKey;
			nextTick(() => {
				const row = rootEl.value?.querySelector<HTMLElement>(`[id="${CSS.escape(key)}"]`);
				if (row) {
					const offset =
						row.getBoundingClientRect().top - el.getBoundingClientRect().top;
					el.scrollTop += offset - anchorOffset;
				}
				anchorKey = null;
			});
		}
	);

	// Oldest-first feed: open at the bottom (newest) on first render.
	let didInitialScroll = false;
	const scrollToBottomOnce = () => {
		if (didInitialScroll || !props.activities.length) return;
		const el = scrollEl.value;
		if (!el) return;
		didInitialScroll = true;
		nextTick(() => {
			el.scrollTop = el.scrollHeight;
		});
	};
	onMounted(scrollToBottomOnce);
	watch(() => props.activities.length, scrollToBottomOnce);
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

// literal lucide-* class for a log / attachment_log gutter dot
function gutterIconClass(activity: LogActivity | AttachmentLogActivity): string {
	const name =
		activity.type === "attachment_log"
			? activity.data.action === "removed"
				? "trash-2"
				: "paperclip"
			: activity.data.icon;
	return LUCIDE_ICON_CLASS[name] ?? "";
}
</script>
