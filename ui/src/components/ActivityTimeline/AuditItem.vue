<template>
	<div class="flex flex-1 items-center gap-1.5 text-base text-ink-gray-5 text-p-sm pt-0.5">
		<!-- audit one-liner: structured text, never v-html -->
		<template v-if="activity.type === 'audit'">
			<span>{{ activity.data.text }}</span>
		</template>
		<!-- attachment log: actor + file (link if available) + private lock -->
		<template v-else>
			<span>
				<span class="font-medium text-ink-gray-8">{{ activity.author.fullname }}</span>
				<span>{{
					activity.data.action === "removed" ? " removed attachment" : " attached"
				}}</span>
			</span>
			<a
				v-if="activity.data.fileUrl"
				:href="activity.data.fileUrl"
				target="_blank"
				class="font-medium text-ink-gray-8 hover:underline"
			>
				{{ activity.data.fileName }}
			</a>
			<span v-else class="font-medium text-ink-gray-8">{{ activity.data.fileName }}</span>
			<span
				v-if="activity.data.isPrivate"
				class="lucide-lock size-3.5 text-ink-amber-3 fill-yellow-400"
			/>
		</template>
		<span>·</span>
		<Tooltip :text="dateFormat(activity.timestamp)">
			<span class="text-sm text-ink-gray-5">{{ timeAgo(activity.timestamp) }}</span>
		</Tooltip>
	</div>
</template>

<script setup lang="ts">
import { Tooltip } from "frappe-ui";
import type { AttachmentLogActivity, AuditActivity } from "./types";
import { dateFormat, timeAgo } from "./utils";

defineProps<{
	activity: AuditActivity | AttachmentLogActivity;
}>();
</script>
