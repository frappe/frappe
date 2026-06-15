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
				:key="activity.key"
				:id="activity.key"
				class="activity mt-2"
			>
				<div
					class="grid w-full grid-cols-[30px_minmax(auto,_1fr)] gap-2 px-6 sm:gap-4 md:px-5"
				>
					<!-- gutter column: vertical connector line + icon/avatar -->
					<div
						class="relative flex justify-center after:absolute after:start-[50%] after:top-3 after:-z-10 after:border-s after:border-outline-gray-modals"
						:class="[i != activities.length - 1 && 'after:h-full']"
					>
						<div
							class="z-1 flex items-center justify-center rounded-full bg-surface-white"
							:class="[activity.type === 'email' ? 'my-1 h-9 w-9' : 'h-6 w-6']"
						>
							<Avatar
								v-if="activity.type === 'email'"
								size="lg"
								:label="activity.senderFullName"
								:image="activity.senderImage"
								class="absolute start-[0.7px] bg-surface-white"
							/>
							<CommentIcon v-else class="absolute start-[7.5px] text-ink-gray-5" />
						</div>
					</div>
					<!-- content column -->
					<div class="mb-4 flex flex-1" :class="[i == activities.length - 1 && 'mb-5']">
						<EmailItem
							v-if="activity.type === 'email'"
							:email="activity"
							:css-href="cssHref"
							:current-user="currentUser"
							class="px-3 py-2"
							@reply="(e) => emit('email:reply', e)"
						/>
						<CommentItem v-else :comment="activity" />
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
import { CommentIcon } from "./icons";
import type { ActivityTimelineProps } from "./types";
import { useDocInfo } from "./useDocInfo";

const props = defineProps<ActivityTimelineProps>();

const emit = defineEmits(["email:reply"]);

const { activities, loading, error, reload } = useDocInfo(props.doctype, props.docname);

defineExpose({ reload });
</script>
