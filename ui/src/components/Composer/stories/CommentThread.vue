<template>
	<div class="rounded-md border border-outline-gray-2 bg-surface-base p-4">
		<div class="flex flex-col gap-4">
			<div v-for="comment in comments" :key="comment.id" class="flex gap-3">
				<Avatar size="md" :label="comment.author" />
				<div class="min-w-0">
					<div class="flex items-baseline gap-2">
						<span class="text-sm-medium text-ink-gray-8">{{ comment.author }}</span>
						<span class="text-p-sm text-ink-gray-4">{{ comment.time }}</span>
					</div>
					<!-- Story-local static HTML only. -->
					<div
						class="prose-sm mt-0.5 max-w-none text-ink-gray-7"
						v-html="comment.body"
					/>
				</div>
			</div>
		</div>

		<div class="mt-4 flex gap-3 border-t border-outline-gray-1 pt-4">
			<Avatar size="md" label="Sydney" />
			<div class="min-w-0 flex-1 rounded-md border border-outline-gray-2">
				<CommentComposer
					ref="composerRef"
					v-model="draft"
					:mentions="teammates"
					@submit="onComment"
				/>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Avatar } from "frappe-ui";
import { CommentComposer } from "../index";
import type { CommentPayload, MentionOption } from "../types";

interface Comment {
	id: number;
	author: string;
	time: string;
	body: string;
}

const comments = ref<Comment[]>([
	{
		id: 1,
		author: "Ada Lovelace",
		time: "3 hours ago",
		body: "<p>Deploy looks good, error rate is back to baseline.</p>",
	},
	{
		id: 2,
		author: "Alan Turing",
		time: "1 hour ago",
		body: "<p>Nice. I'll close the incident after one more quiet hour.</p>",
	},
]);

const teammates: MentionOption[] = [
	{ label: "Ada Lovelace", value: "ada@example.com" },
	{ label: "Alan Turing", value: "alan@example.com" },
	{ label: "Katherine Johnson", value: "katherine@example.com" },
];

const draft = ref("");
const composerRef = ref<InstanceType<typeof CommentComposer> | null>(null);

function onComment(payload: CommentPayload) {
	comments.value.push({
		id: Date.now(),
		author: "Sydney",
		time: "Just now",
		body: payload.body,
	});
	composerRef.value?.reset();
}
</script>
