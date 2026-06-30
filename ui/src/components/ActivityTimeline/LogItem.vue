<template>
	<!-- ps-[13px] aligns row text with the card text (1px border + px-3) -->
	<div
		class="flex flex-1 flex-col gap-2 ps-[13px] text-sm font-medium leading-6 text-ink-gray-6"
	>
		<!-- grouped: collapsible "+N changes" header + per-row lines -->
		<template v-if="group.length > 1">
			<div class="flex items-center gap-1.5">
				<button
					type="button"
					class="flex items-center gap-1.5 hover:text-ink-gray-7"
					@click="expanded = !expanded"
				>
					<span class="text-ink-gray-5">
						<!-- reserve the wider word's width so toggling doesn't reflow -->
						<span class="inline-grid justify-items-start align-baseline">
							<span class="invisible col-start-1 row-start-1" aria-hidden="true"
								>Show</span
							>
							<span class="invisible col-start-1 row-start-1" aria-hidden="true"
								>Hide</span
							>
							<span class="col-start-1 row-start-1">{{
								expanded ? "Hide" : "Show"
							}}</span>
						</span>
						<span class="font-medium text-ink-gray-8">
							+{{ group.length }} changes
						</span>
						from
						<span class="font-medium text-ink-gray-8">{{
							activity.author?.fullname
						}}</span>
					</span>
					<FeatherIcon
						:name="expanded ? 'chevron-up' : 'chevron-down'"
						class="size-3.5"
					/>
				</button>
				<span>·</span>
				<Tooltip :text="dateFormat(activity.timestamp)">
					<span class="text-sm text-ink-gray-5">{{ timeAgo(activity.timestamp) }}</span>
				</Tooltip>
			</div>
			<div v-if="expanded" class="flex flex-col gap-2">
				<div v-for="row in group" :key="row.key" class="flex items-center gap-1.5">
					<ActorText :activity="row" />
					<span>·</span>
					<Tooltip :text="dateFormat(row.timestamp)">
						<span class="text-sm text-ink-gray-5">{{ timeAgo(row.timestamp) }}</span>
					</Tooltip>
				</div>
			</div>
		</template>

		<!-- single row: log one-liner or attachment log -->
		<div v-else class="flex items-center gap-1.5">
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
				<span v-if="activity.data.isPrivate" class="lucide-lock size-3.5" />
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
			<span>·</span>
			<Tooltip :text="dateFormat(activity.timestamp)">
				<span class="text-sm text-ink-gray-5">{{ timeAgo(activity.timestamp) }}</span>
			</Tooltip>
		</div>
	</div>
</template>

<script setup lang="ts">
import { FeatherIcon, Tooltip } from "frappe-ui";
import { computed, h, ref } from "vue";
import type { AttachmentLogActivity, LogActivity } from "./types";
import { dateFormat, splitBold, timeAgo } from "./utils";

const props = defineProps<{
	activity: LogActivity | AttachmentLogActivity;
}>();

// only `log` activities carry a group
const group = computed<LogActivity[]>(() =>
	props.activity.type === "log" ? props.activity.data.group ?? [] : []
);

const expanded = ref(false);

// bolds actor + assignee (backend-supplied; no message-template parsing)
const ActorText = ({ activity }: { activity: LogActivity }) => {
	const { author, data } = activity;
	const segments = splitBold(data.text ?? "", [author?.fullname, data.assignee]);
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
