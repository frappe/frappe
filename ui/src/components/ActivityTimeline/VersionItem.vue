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
					<span class="text-ink-gray-5">
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
				<VersionChange
					v-for="c in changes"
					:key="c.name"
					:change="c"
					:author="activity.author.fullname"
				/>
			</div>
		</template>

		<!-- single change: author + change on one line, history stacked left-aligned below -->
		<div v-else class="flex flex-col gap-1">
			<div class="flex items-start gap-1.5">
				<span class="font-medium text-ink-gray-8">{{ activity.author.fullname }}</span>
				<VersionChange
					v-model:open="open"
					:change="changes[0]"
					:show-history="false"
					class="min-w-0 flex-1"
				/>
				<div class="ms-auto whitespace-nowrap">
					<Tooltip :text="dateFormat(activity.timestamp)">
						<span class="text-sm text-ink-gray-5">{{
							timeAgo(activity.timestamp)
						}}</span>
					</Tooltip>
				</div>
			</div>
			<VersionChangeHistory
				v-if="open && singleHistory"
				:history="singleHistory"
				:author="activity.author.fullname"
				:prefix="singlePrefix"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { FeatherIcon, Tooltip } from "frappe-ui";
import { computed, ref } from "vue";
import type { VersionActivity, VersionChange as VersionChangeType } from "./types";
import { dateFormat, timeAgo } from "./utils";
import VersionChange from "./VersionChange.vue";
import VersionChangeHistory from "./VersionChangeHistory.vue";

const props = defineProps<{
	activity: VersionActivity;
}>();

// grouped → `group`; otherwise the single change itself
const changes = computed<VersionChangeType[]>(
	() => props.activity.data.group ?? [props.activity.data]
);

// single-change history (>1 field change) lifted out to render left-aligned under the author
const singleHistory = computed(() => {
	const c = changes.value[0];
	return c?.type === "diff" && (c.history?.length ?? 0) > 1 ? c.history! : null;
});
const singlePrefix = computed(() => {
	const c = changes.value[0];
	return c?.type === "diff" ? c.prefix : "";
});

// grouped "+N changes" toggle; `open` drives the single-change history chevron
const expanded = ref(false);
const open = ref(false);
</script>
