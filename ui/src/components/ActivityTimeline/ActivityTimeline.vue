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
				v-for="(activity, i) in orderedActivities"
				:key="activity.key"
				:id="activity.key"
				class="activity mt-2"
			>
				<div
					class="grid w-full grid-cols-[30px_minmax(auto,_1fr)] gap-2 px-6 sm:gap-4 md:px-0"
				>
					<!-- gutter column: vertical connector line + icon/avatar -->
					<div
						class="relative flex justify-center after:absolute after:start-[50%] after:top-3 after:-z-10 after:border-s after:border-outline-gray-modals"
						:class="[
							i != orderedActivities.length - 1 && 'after:h-full',
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
							<Avatar
								v-if="activity.type === 'email'"
								size="lg"
								:label="activity.senderFullName"
								:image="activity.senderImage"
								class="absolute start-[0.7px] bg-surface-white"
							/>
							<template
								v-else-if="
									activity.type === 'audit' || activity.type === 'attachment_log'
								"
							>
								<DotIcon
									v-if="
										activity.type === 'audit' &&
										(activity.subtype === 'assigned' ||
											activity.subtype === 'assignment_completed')
									"
									class="text-ink-gray-5"
								/>
								<span
									v-else
									:class="[gutterIconClass(activity), 'size-4 text-ink-gray-5']"
								/>
							</template>
							<CommentIcon v-else class="absolute start-[7.5px] text-ink-gray-5" />
						</div>
					</div>
					<!-- content column -->
					<div
						class="mb-4 flex flex-1"
						:class="[
							i == orderedActivities.length - 1 && 'mb-5',
							isOneLiner(activity) && 'mt-[2px]',
						]"
					>
						<EmailItem
							v-if="activity.type === 'email'"
							:email="activity"
							:css-href="cssHref"
							:current-user="currentUser"
							class="px-3 py-2"
							@reply="(e) => emit('email:reply', e)"
						/>
						<CommentItem v-else-if="activity.type === 'comment'" :comment="activity" />
						<AuditItem
							v-else-if="
								activity.type === 'audit' || activity.type === 'attachment_log'
							"
							:activity="activity"
						/>
					</div>
				</div>
			</div>
		</div>
	</div>
	<!-- Realtime (later): subscribe to docinfo_update for doctype/docname and reload() -->
</template>

<script setup lang="ts">
import { Avatar, ErrorMessage, FeatherIcon, LoadingIndicator } from "frappe-ui";
import { computed } from "vue";
import AuditItem from "./AuditItem.vue";
import CommentItem from "./CommentItem.vue";
import EmailItem from "./EmailItem.vue";
import { CommentIcon, DotIcon, LUCIDE_ICON_CLASS } from "./icons";
import type {
	Activity,
	ActivityTimelineProps,
	AttachmentLogActivity,
	AuditActivity,
} from "./types";
import { useDocInfo } from "./useDocInfo";

const props = withDefaults(defineProps<ActivityTimelineProps>(), {
	order: "desc",
});

// one-line activity rows (audit/attachment) align differently from the cards
// (email/comment) — nudged to vertically center the icon with the single line
function isOneLiner(activity: Activity): boolean {
	return activity.type === "audit" || activity.type === "attachment_log";
}

// literal lucide-* class for an audit / attachment_log gutter dot
function gutterIconClass(activity: AuditActivity | AttachmentLogActivity): string {
	const name =
		activity.type === "attachment_log"
			? activity.action === "removed"
				? "trash-2"
				: "paperclip"
			: activity.icon;
	return LUCIDE_ICON_CLASS[name] ?? "";
}

const emit = defineEmits(["email:reply"]);

const { activities, loading, error, reload } = useDocInfo(props.doctype, props.docname);

// transform sorts ascending (canonical, shared cache); apply display order here
const orderedActivities = computed(() =>
	props.order === "desc" ? [...activities.value].reverse() : activities.value
);

defineExpose({ reload });
</script>
