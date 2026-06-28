<template>
	<!-- ps-[13px] aligns the row text with the email/comment card text (1px border + px-3) -->
	<div
		class="flex flex-1 flex-col gap-2 ps-[13px] text-sm font-medium leading-6 text-ink-gray-6"
	>
		<!-- grouped: >1 change -->
		<template v-if="changes.length > 1">
			<div class="flex items-center gap-1.5">
				<button
					type="button"
					class="flex items-center gap-2 hover:text-ink-gray-7"
					@click="expanded = !expanded"
				>
					<span>
						<span>Show</span>
						<span class="font-medium text-ink-gray-8">
							+{{ changes.length }} changes
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
			<div v-if="expanded" class="flex flex-col gap-2">
				<VersionChange v-for="c in changes" :key="c.name" :change="c" />
			</div>
		</template>

		<!-- single change -->
		<div v-else class="flex items-start gap-1.5">
			<span class="font-medium text-ink-gray-8">{{ activity.author.fullname }}</span>
			<VersionChange :change="changes[0]" />
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
import { computed, ref } from "vue";
import type { VersionActivity, VersionChange as VersionChangeType } from "./types";
import { dateFormat, timeAgo } from "./utils";
import VersionChange from "./VersionChange.vue";

const props = defineProps<{
	activity: VersionActivity;
}>();

// grouped → `group`; otherwise the single change itself
const changes = computed<VersionChangeType[]>(
	() => props.activity.data.group ?? [props.activity.data]
);

const expanded = ref(false);
</script>
