<template>
	<!-- ps-[13px] aligns the row text with the email/comment card text (1px border + px-3) -->
	<div
		class="flex flex-1 flex-col gap-2 ps-[13px] text-sm font-medium leading-6 text-ink-gray-5"
	>
		<!-- grouped: collapsible "+N changes" header + per-row lines, folded when
		     consecutive same-author log rows share a run. Mirrors VersionItem, but
		     keeps LogItem's inline `·` + timeago styling. -->
		<template v-if="group.length > 1">
			<div class="flex items-center gap-1.5">
				<button
					type="button"
					class="flex items-center gap-1.5 hover:text-ink-gray-7"
					@click="expanded = !expanded"
				>
					<span>
						<!-- reserve the wider word's width so toggling doesn't reflow the line -->
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
				<div v-for="g in group" :key="g.key" class="flex items-center gap-1.5">
					<span>{{ g.data.text }}</span>
					<span>·</span>
					<Tooltip :text="dateFormat(g.timestamp)">
						<span class="text-sm text-ink-gray-5">{{ timeAgo(g.timestamp) }}</span>
					</Tooltip>
				</div>
			</div>
		</template>

		<!-- single row: log one-liner or attachment log -->
		<div v-else class="flex items-center gap-1.5">
			<!-- log one-liner: structured text, never v-html -->
			<template v-if="activity.type === 'log'">
				<span>{{ activity.data.text }}</span>
			</template>
			<!-- attachment log: actor + file (link if available) + private lock -->
			<template v-else>
				<span>
					<span class="font-medium text-ink-gray-6">{{ activity.author.fullname }}</span>
					<span>{{
						activity.data.action === "removed" ? " removed attachment" : " attached"
					}}</span>
				</span>
				<span v-if="activity.data.isPrivate" class="lucide-lock size-3.5" />
				<a
					v-if="activity.data.fileUrl"
					:href="activity.data.fileUrl"
					target="_blank"
					class="font-medium text-ink-gray-5 hover:underline"
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
import { computed, ref } from "vue";
import type { AttachmentLogActivity, LogActivity } from "./types";
import { dateFormat, timeAgo } from "./utils";

const props = defineProps<{
	activity: LogActivity | AttachmentLogActivity;
}>();

// only `log` activities carry an optional collapsible group; attachments never do
const group = computed<LogActivity[]>(() =>
	props.activity.type === "log" ? props.activity.data.group ?? [] : []
);

const expanded = ref(false);
</script>
