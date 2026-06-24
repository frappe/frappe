<template>
	<div class="activity-timeline">
		<!-- spinner only on first load; background revalidation keeps cached data visible -->
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
				v-for="(activity, i) in activities"
				:key="getKey(activity, i)"
				:id="getKey(activity, i)"
				class="activity mt-2"
			>
				<div
					class="grid w-full grid-cols-[30px_minmax(auto,_1fr)] gap-2 px-6 sm:gap-4 md:px-0"
				>
					<!-- gutter column: vertical connector line + icon/avatar -->
					<div
						class="relative flex justify-center after:absolute after:start-[50%] after:top-3 after:-z-10 after:border-s after:border-outline-gray-modals"
						:class="[
							i != activities.length - 1 && 'after:h-full',
							isOneLiner(activity) && 'after:top-6',
						]"
					>
						<div
							class="z-1 flex items-center justify-center rounded-full bg-surface-white"
							:class="[
								activity.type === 'email' ? 'my-1 h-9 w-9' : 'h-6 w-6',
								isOneLiner(activity) && 'mt-[2px]',
							]"
						>
							<!-- gutter ladder: #icon-{type} slot > envelope icon > per-type default -->
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
									<Avatar
										v-if="activity.type === 'email'"
										size="lg"
										:label="activity.author.fullname"
										:image="activity.author.image"
										class="absolute start-[0.7px] bg-surface-white"
									/>
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
					<!-- content column -->
					<div
						class="mb-4 flex flex-1"
						:class="[
							i == activities.length - 1 && 'mb-5',
							isOneLiner(activity) && 'mt-[2px]',
						]"
						:data-type="activity.type"
					>
						<slot :name="`item-${activity.type}`" :activity="activity">
							<!-- default slot: full per-row override, exposes the row as { item } -->
							<slot :item="activity">
								<EmailItem
									v-if="activity.type === 'email'"
									:email="activity"
									class="px-3 py-2"
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
	</div>
	<!-- Realtime (later): subscribe to docinfo_update for doctype/docname and reload() -->
</template>

<script setup lang="ts">
import { Avatar, ErrorMessage, FeatherIcon, LoadingIndicator } from "frappe-ui";
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
import VersionItem from "./VersionItem.vue";

withDefaults(defineProps<ActivityTimelineProps>(), {
	loading: false,
	error: null,
});

// Stable v-for key / scroll-target id. Built-ins always carry `key`; a custom
// row may omit it — fall back to type+timestamp (stable across reorders when a
// timestamp exists), then to the index as a last resort.
function getKey(activity: Activity | CustomActivity, index: number): string {
	return (
		activity.key ??
		(activity.timestamp
			? `${activity.type}:${activity.timestamp}`
			: `${activity.type}:${index}`)
	);
}

// one-line activity rows (log/attachment) align differently from the cards
// (email/comment) — nudged to vertically center the icon with the single line
function isOneLiner(activity: Activity): boolean {
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
