<template>
	<div class="flex-1 flex-col text-base">
		<div class="mb-2 flex items-center justify-between">
			<div class="flex items-center gap-2 text-ink-gray-5">
				<Avatar size="md" :label="comment.author.fullname" :image="comment.author.image" />
				<p>
					<span class="font-medium text-ink-gray-8">{{ comment.author.fullname }}</span>
					<span> commented</span>
				</p>
			</div>
			<Tooltip :text="dateFormat(comment.timestamp)">
				<span class="ps-0.5 text-sm text-ink-gray-5">
					{{ timeAgo(comment.timestamp) }}
				</span>
			</Tooltip>
		</div>
		<!-- content is sanitized server-side by Comment.validate -->
		<!-- note: helpdesk applied a per-content font here (:class="getFontFamily(content)",
		     Arabic → system-ui); dropped for now, re-add a :class override if needed -->
		<div class="rounded-md bg-surface-gray-1 px-3 py-1.5 transition-colors">
			<div class="prose-f content text-p-sm" v-html="comment.content" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { Avatar, Tooltip } from "frappe-ui";
import type { CommentActivity } from "./types";
import { dateFormat, timeAgo } from "./utils";

defineProps<{
	comment: CommentActivity;
}>();
</script>
