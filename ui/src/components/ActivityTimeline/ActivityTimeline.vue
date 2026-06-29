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
		<template v-else>
			<!-- older emails load at the top on scroll-up -->
			<div v-if="paginate?.isFetchingNextPage" class="flex justify-center py-2">
				<LoadingIndicator class="size-5 text-ink-gray-5" />
			</div>
			<div class="activities mt-0.5">
				<div
					v-for="(activity, i) in activities"
					:key="getKey(activity, i)"
					:id="getKey(activity, i)"
					class="activity mt-2"
					:tabindex="0"
				>
					<div class="grid w-full grid-cols-[30px_minmax(auto,_1fr)] gap-2 px-6 md:px-0">
						<!-- gutter column: vertical connector line + icon/avatar -->
						<div
							class="relative flex justify-center after:absolute after:start-[50%] after:top-3 after:-z-10 after:border-s after:border-outline-gray-modals"
							:class="[
								i != activities.length - 1 && 'after:h-full',
								isOneLinerActivity(activity) && 'after:top-6',
							]"
						>
							<div
								class="z-1 flex items-center justify-center self-start bg-surface-white"
								:class="[
									isAvatarActivity(activity) ? 'h-10' : 'h-6 w-6 rounded-full',
								]"
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
							:class="[i == activities.length - 1 && 'mb-5']"
							:data-type="activity.type"
						>
							<slot :name="`item-${activity.type}`" :activity="activity">
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
			</div>
		</template>
	</div>
	<!-- Realtime (later): subscribe to docinfo_update for doctype/docname and reload() -->
</template>

<script setup lang="ts">
import { Avatar, ErrorMessage, FeatherIcon, LoadingIndicator } from "frappe-ui";
import { nextTick, onMounted, ref, watch } from "vue";
import CommentItem from "./CommentItem.vue";
import EmailItem from "./EmailItem.vue";
import { CommentIcon, DotIcon, LUCIDE_ICON_CLASS } from "./icons";
import { useLoadMoreOnScroll } from "./useLoadMoreOnScroll";
// email badge; needs `frappeui({ lucideIcons: true })` in the consumer's vite config
import MailIcon from "~icons/lucide/mail";
import LogItem from "./LogItem.vue";
import type {
	Activity,
	ActivityTimelineProps,
	AttachmentLogActivity,
	CustomActivity,
	LogActivity,
} from "./types";
import VersionItem from "./VersionItem.vue";

const props = withDefaults(defineProps<ActivityTimelineProps>(), {
	loading: false,
	error: null,
});

// Reverse infinite scroll for emails — only wired when pagination is enabled.
const rootEl = ref<HTMLElement | null>(null);
// scrollHeight at fetch time; anchors the viewport after older rows prepend.
let prevScrollHeight = 0;

if (props.paginate) {
	const { scrollEl } = useLoadMoreOnScroll(rootEl, {
		canLoadMore: () => !!props.paginate?.hasNextPage && !props.paginate?.isFetchingNextPage,
		loadMore: () => {
			prevScrollHeight = scrollEl.value?.scrollHeight ?? 0;
			props.paginate?.fetchNextPage();
		},
	});

	// after older rows patch in, push scrollTop down by the height gained to stay anchored
	watch(
		() => props.activities.length,
		() => {
			const el = scrollEl.value;
			if (!el || !prevScrollHeight) return;
			nextTick(() => {
				el.scrollTop += el.scrollHeight - prevScrollHeight;
				prevScrollHeight = 0;
			});
		}
	);

	// Oldest-first feed: open at the bottom (newest) on first render, then let
	// scroll-up paging take over — also stops the top trigger firing on mount.
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
	onMounted(scrollToBottomOnce); // cached/synchronous first page
	watch(() => props.activities.length, scrollToBottomOnce); // async first page
}

// Stable v-for key / scroll-target id. Custom rows may omit `key` — fall back to
// type+timestamp, then index.
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
