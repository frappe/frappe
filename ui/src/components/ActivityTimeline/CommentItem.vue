<template>
	<div class="flex-1 flex-col text-base">
		<!-- header / actions / footer slots: override a region, or leave it to the
		     default markup. Reach them by rendering this component inside
		     ActivityTimeline's #item-comment slot. -->
		<div class="mb-2 flex items-start justify-between gap-2">
			<div class="min-w-0 flex-1">
				<slot name="header" :comment="comment">
					<div class="flex items-center justify-between gap-2">
						<div class="flex items-center gap-2 text-ink-gray-5">
							<Avatar
								size="md"
								:label="comment.author.fullname"
								:image="comment.author.image"
							/>
							<p>
								<span class="font-medium text-ink-gray-8">{{
									comment.author.fullname
								}}</span>
								<span> commented</span>
							</p>
						</div>
						<Tooltip :text="dateFormat(comment.timestamp)">
							<span class="ps-0.5 text-sm text-ink-gray-5">
								{{ timeAgo(comment.timestamp) }}
							</span>
						</Tooltip>
					</div>
				</slot>
			</div>
			<!-- #actions exposes the default actions as `actions`; by default they
			     render in a triple-dot dropdown (edit / delete). -->
			<div class="flex shrink-0 items-center gap-1">
				<slot name="actions" :comment="comment" :actions="actions">
					<Dropdown
						:options="
							actions.map((a) => ({
								label: a.label,
								icon: a.icon,
								onClick: a.onClick,
							}))
						"
						placement="right"
					>
						<Button variant="ghost" icon="more-horizontal" class="!h-6 !w-6" />
					</Dropdown>
				</slot>
			</div>
		</div>
		<!-- content is sanitized server-side by Comment.validate -->
		<!-- note: helpdesk applied a per-content font here (:class="getFontFamily(content)",
		     Arabic → system-ui); dropped for now, re-add a :class override if needed -->
		<div class="rounded-md bg-surface-gray-1 px-3 py-1.5 transition-colors">
			<div class="prose-f content text-p-sm" v-html="comment.data.content" />
		</div>
		<slot name="footer" :comment="comment" />
	</div>
</template>

<script setup lang="ts">
import { Avatar, Button, Dropdown, Tooltip } from "frappe-ui";
import { computed } from "vue";
import type { CommentActivity, TimelineAction } from "./types";
import { dateFormat, timeAgo } from "./utils";

const props = defineProps<{
	comment: CommentActivity;
}>();

const emit = defineEmits<{
	edit: [CommentActivity];
	delete: [CommentActivity];
}>();

// default actions, also handed to the #actions slot so a consumer can render
// these alongside (or instead of) its own
const actions = computed<TimelineAction[]>(() => [
	{ key: "edit", label: "Edit", icon: "edit-2", onClick: () => emit("edit", props.comment) },
	{
		key: "delete",
		label: "Delete",
		icon: "trash-2",
		theme: "red",
		onClick: () => emit("delete", props.comment),
	},
]);
</script>
