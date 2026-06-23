<template>
	<div class="flex flex-1 flex-col gap-1 pt-0.5 text-base text-ink-gray-5 text-p-sm">
		<!-- grouped: collapsible header + per-change rows -->
		<template v-if="activity.data.group && activity.data.group.length > 1">
			<div class="flex items-center gap-1.5">
				<button
					type="button"
					class="flex items-center gap-1 hover:text-ink-gray-7"
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
							+{{ activity.data.group.length }} changes
						</span>
						from
						<span class="font-medium text-ink-gray-8">{{
							activity.author.fullname
						}}</span>
					</span>
					<FeatherIcon
						:name="expanded ? 'chevron-up' : 'chevron-down'"
						class="size-3.5"
					/>
				</button>
				<div class="ms-auto whitespace-nowrap">
					<Tooltip :text="dateFormat(activity.timestamp)">
						<span class="text-sm text-ink-gray-5">{{
							timeAgo(activity.timestamp)
						}}</span>
					</Tooltip>
				</div>
			</div>
			<div v-if="expanded" class="flex flex-col gap-1">
				<div
					v-for="g in activity.data.group"
					:key="g.key"
					class="flex items-center gap-1.5"
				>
					<span>
						<span class="font-medium text-ink-gray-8">{{ g.author.fullname }}</span>
						{{ " " }}{{ g.data.text }}
					</span>
					<div class="ms-auto whitespace-nowrap">
						<Tooltip :text="dateFormat(g.timestamp)">
							<span class="text-sm text-ink-gray-5">{{ timeAgo(g.timestamp) }}</span>
						</Tooltip>
					</div>
				</div>
			</div>
		</template>

		<!-- single change -->
		<div v-else class="flex items-center gap-1.5">
			<span>
				<span class="font-medium text-ink-gray-8">{{ activity.author.fullname }}</span>
				{{ " " }}{{ activity.data.text }}
			</span>
			<div class="ms-auto whitespace-nowrap">
				<Tooltip :text="dateFormat(activity.timestamp)">
					<span class="text-sm text-ink-gray-5">{{ timeAgo(activity.timestamp) }}</span>
				</Tooltip>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { FeatherIcon, Tooltip } from "frappe-ui";
import { ref } from "vue";
import type { VersionActivity } from "./types";
import { dateFormat, timeAgo } from "./utils";

defineProps<{
	activity: VersionActivity;
}>();

const expanded = ref(false);
</script>
