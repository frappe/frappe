<template>
	<div class="flex-1 flex-col text-base">
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
			<div v-if="$slots.actions && !editable" class="flex shrink-0 items-center gap-1">
				<slot name="actions" />
			</div>
		</div>
		<div class="rounded-md bg-surface-gray-1 px-3 py-1.5 transition-colors">
			<TextEditor
				:content="comment.data.content"
				:editable="editable"
				editor-class="p-1 prose-sm"
				@change="editedContent = $event"
			/>
		</div>
		<div v-if="editable" class="mt-2 flex justify-end gap-2">
			<Button variant="outline" label="Discard" @click="emit('discard')" />
			<Button variant="solid" label="Save" @click="emit('save', editedContent)" />
		</div>
		<slot v-else name="footer" :comment="comment" />
	</div>
</template>

<script setup lang="ts">
import { Avatar, Button, TextEditor, Tooltip } from "frappe-ui";
import { ref } from "vue";
import type { CommentActivity } from "./types";
import { dateFormat, timeAgo } from "./utils";

const props = withDefaults(
	defineProps<{
		comment: CommentActivity;
		editable?: boolean;
	}>(),
	{
		editable: false,
	}
);

const emit = defineEmits<{
	save: [content: string];
	discard: [];
}>();

const editedContent = ref(props.comment.data.content);
</script>
