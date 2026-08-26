<template>
	<div class="rounded-md border border-outline-gray-2 bg-surface-base">
		<div class="flex items-center justify-between border-b border-outline-gray-2 px-4 py-3">
			<div>
				<div class="text-base font-medium text-ink-gray-9">
					Cannot access my invoices after the update
				</div>
				<div class="text-p-sm text-ink-gray-5">TICKET-1042 · grace@example.com</div>
			</div>
			<Badge label="Open" theme="orange" variant="subtle" />
		</div>

		<div class="flex flex-col gap-4 px-4 py-4">
			<div v-for="message in messages" :key="message.id" class="flex gap-3">
				<Avatar size="md" :label="message.author" />
				<div class="min-w-0">
					<div class="flex items-baseline gap-2">
						<span class="text-sm-medium text-ink-gray-8">{{ message.author }}</span>
						<Badge
							v-if="message.internal"
							label="Internal"
							theme="gray"
							variant="subtle"
						/>
						<span class="text-p-sm text-ink-gray-4">{{ message.time }}</span>
					</div>
					<!-- Story-local static HTML only. -->
					<div
						class="prose-sm mt-0.5 max-w-none text-ink-gray-7"
						v-html="message.body"
					/>
				</div>
			</div>
		</div>

		<!-- FloatingWindow: docked renders in-flow; pop-out moves the same instance. -->
		<div class="px-4 pb-4">
			<FloatingWindow title="TICKET-1042 Reply" :minimizable="false">
				<!-- Full-height column: the composer stretches, so its toolbar row
				     pins to the window bottom while floating. -->
				<div class="flex h-full min-h-0 flex-col">
					<div class="shrink-0 px-2.5 pt-2">
						<TabButtons v-model="channel" :options="channelOptions" />
					</div>
					<!-- v-show keeps both mounted so each draft survives a tab switch. -->
					<div
						v-show="channel === 'reply'"
						class="flex min-h-0 flex-1 flex-col px-2.5 py-2"
					>
						<EmailComposer
							ref="replyRef"
							v-model="replyBody"
							v-model:to="to"
							v-model:cc="cc"
							v-model:bcc="bcc"
							v-model:quoted="quoted"
							class="min-h-0 flex-1"
							:search-recipients="searchRecipients"
							placeholder="Reply to Grace…"
							@submit="onReply"
						/>
					</div>
					<div v-show="channel === 'comment'" class="flex min-h-0 flex-1 flex-col py-2">
						<CommentComposer
							ref="commentRef"
							v-model="commentBody"
							class="min-h-0 flex-1"
							:mentions="agents"
							@submit="onComment"
						/>
					</div>
				</div>
			</FloatingWindow>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Avatar, Badge, TabButtons } from "frappe-ui";
import { FloatingWindow } from "frappe-ui/experimental";
import { CommentComposer, EmailComposer } from "../index";
import type { CommentPayload, EmailPayload, MentionOption, Recipient } from "../types";

interface Message {
	id: number;
	author: string;
	time: string;
	body: string;
	internal?: boolean;
}

const messages = ref<Message[]>([
	{
		id: 1,
		author: "Grace Hopper",
		time: "2 days ago",
		body: "<p>Since the update I get a blank page when I open Billing → Invoices.</p>",
	},
	{
		id: 2,
		author: "Sydney",
		time: "1 day ago",
		body: "<p>Thanks for the report! Could you tell me which browser you're on?</p>",
	},
]);

const channel = ref("reply");
const channelOptions = [
	{ label: "Reply", value: "reply" },
	{ label: "Comment", value: "comment" },
];

const replyBody = ref("");
const commentBody = ref("");
const to = ref<Recipient[]>([{ email: "grace@example.com", label: "Grace Hopper" }]);
const cc = ref<Recipient[]>([]);
const bcc = ref<Recipient[]>([]);
// The last customer message, rendered as a collapsible block and appended on send.
const quoted = ref<string | null>(messages.value[0].body);

const agents: MentionOption[] = [
	{ label: "Ada Lovelace", value: "ada@example.com" },
	{ label: "Alan Turing", value: "alan@example.com" },
];

const directory: Recipient[] = [
	{ label: "Grace Hopper", email: "grace@example.com" },
	{ label: "Katherine Johnson", email: "katherine@example.com" },
];
async function searchRecipients(query: string): Promise<Recipient[]> {
	const text = query.trim().toLowerCase();
	if (!text) return directory;
	return directory.filter((person) => person.label!.toLowerCase().includes(text));
}

const replyRef = ref<InstanceType<typeof EmailComposer> | null>(null);
const commentRef = ref<InstanceType<typeof CommentComposer> | null>(null);

function onReply(payload: EmailPayload) {
	messages.value.push({
		id: Date.now(),
		author: "Sydney",
		time: "Just now",
		body: payload.body,
	});
	quoted.value = null;
	replyRef.value?.reset();
}

function onComment(payload: CommentPayload) {
	messages.value.push({
		id: Date.now(),
		author: "Sydney",
		time: "Just now",
		body: payload.body,
		internal: true,
	});
	commentRef.value?.reset();
}
</script>
