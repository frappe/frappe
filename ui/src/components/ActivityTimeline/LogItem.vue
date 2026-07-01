<template>
	<!-- ps-[13px] aligns row text with the card text (1px border + px-3) -->
	<div
		class="flex flex-1 flex-col gap-2 ps-[13px] text-sm font-medium leading-6 text-ink-gray-6"
	>
		<!-- log one-liner or attachment log -->
		<div class="flex items-center gap-1.5">
			<!-- structured text, never v-html -->
			<ActorText v-if="activity.type === 'log'" :activity="activity" />
			<template v-else>
				<span class="text-ink-gray-5">
					<span class="font-medium text-ink-gray-8">{{
						activity?.author?.fullname
					}}</span>
					<span>{{
						activity.data.action === "removed" ? " removed attachment" : " attached"
					}}</span>
				</span>
				<LucideLock v-if="activity.data.isPrivate" class="size-3.5" />
				<a
					v-if="activity.data.fileUrl"
					:href="activity.data.fileUrl"
					target="_blank"
					class="font-medium text-ink-gray-8 hover:text-ink-blue-2"
				>
					{{ activity.data.fileName }}
				</a>
				<span v-else class="font-medium text-ink-gray-5">{{
					activity.data.fileName
				}}</span>
			</template>
			<TimeAgo :timestamp="activity.timestamp" class="text-sm ml-auto" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { h } from "vue";
import LucideLock from "~icons/lucide/lock";
import TimeAgo from "./TimeAgo.vue";
import type { AttachmentLogActivity, LogActivity } from "./types";
import { splitBold } from "./utils";

defineProps<{
	activity: LogActivity | AttachmentLogActivity;
}>();

// bolds actor + assignee (backend-supplied; no message-template parsing)
const ActorText = ({ activity }: { activity: LogActivity }) => {
	const { author, data } = activity;
	const segments = splitBold(data.text ?? "", [
		author?.fullname,
		data.assignee,
		...(data.assignees ?? []),
	]);
	return h(
		"span",
		{ class: "text-ink-gray-5" },
		segments.map((seg) =>
			seg.bold
				? h("span", { class: "font-medium text-ink-gray-8" }, `${seg.text} `)
				: `${seg.text} `
		)
	);
};
</script>
