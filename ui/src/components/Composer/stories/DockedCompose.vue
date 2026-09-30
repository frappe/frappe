<template>
	<div class="rounded-md border border-outline-gray-2 p-4">
		<p v-if="lastSent" class="mb-3 text-p-sm text-ink-gray-5">Sent “{{ lastSent }}” ✓</p>
		<!-- FloatingWindow brings dock, float, and minimize; the draft rides along. -->
		<FloatingWindow title="New message">
			<!-- h-full so the composer's toolbar pins to the window bottom while floating. -->
			<EmailComposer
				ref="composerRef"
				class="h-full"
				v-model="body"
				v-model:to="to"
				v-model:subject="subject"
				v-model:from="from"
				show-from
				show-subject
				:senders="senders"
				:search-recipients="searchRecipients"
				placeholder="Write your email…"
				@submit="onSend"
			/>
		</FloatingWindow>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { FloatingWindow } from "frappe-ui/experimental";
import { EmailComposer } from "../index";
import type { EmailPayload, Recipient } from "../types";

const lastSent = ref("");

const body = ref("");
const subject = ref("");
const from = ref("");
const to = ref<Recipient[]>([]);

const senders: Recipient[] = [
	{ label: "Support", email: "support@example.com" },
	{ label: "Sales", email: "sales@example.com" },
];

const directory: Recipient[] = [
	{ label: "Grace Hopper", email: "grace@example.com" },
	{ label: "Ada Lovelace", email: "ada@example.com" },
	{ label: "Alan Turing", email: "alan@example.com" },
];
async function searchRecipients(query: string): Promise<Recipient[]> {
	const text = query.trim().toLowerCase();
	if (!text) return directory;
	return directory.filter((person) => person.label!.toLowerCase().includes(text));
}

const composerRef = ref<InstanceType<typeof EmailComposer> | null>(null);

function onSend(payload: EmailPayload) {
	lastSent.value = payload.subject || payload.to[0]?.email || "email";
	composerRef.value?.reset();
}
</script>
