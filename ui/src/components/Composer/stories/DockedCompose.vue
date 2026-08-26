<template>
	<div class="flex h-24 items-center gap-3 rounded-md border border-outline-gray-2 p-4">
		<Button variant="solid" label="New email" @click="open = true" />
		<span v-if="lastSent" class="text-p-sm text-ink-gray-5">Sent “{{ lastSent }}” ✓</span>
	</div>

	<!-- The window is host chrome (FP1): a fixed card around the inline composer. -->
	<div
		v-if="open"
		class="fixed bottom-0 right-6 z-30 w-[440px] overflow-hidden rounded-t-xl border border-b-0 border-outline-gray-3 bg-surface-base shadow-2xl"
	>
		<div
			class="flex items-center justify-between border-b border-outline-gray-2 bg-surface-gray-2 py-1 pl-3 pr-1"
		>
			<span class="text-sm-medium text-ink-gray-8">New message</span>
			<div class="flex items-center">
				<Button
					variant="ghost"
					:icon="collapsed ? LucideChevronUp : LucideMinus"
					:aria-label="collapsed ? 'Expand' : 'Minimize'"
					@click="collapsed = !collapsed"
				/>
				<Button variant="ghost" :icon="LucideX" aria-label="Close" @click="open = false" />
			</div>
		</div>

		<div v-show="!collapsed">
			<EmailComposer
				ref="composerRef"
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
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Button } from "frappe-ui";
import LucideChevronUp from "~icons/lucide/chevron-up";
import LucideMinus from "~icons/lucide/minus";
import LucideX from "~icons/lucide/x";
import { EmailComposer } from "../index";
import type { EmailPayload, Recipient } from "../types";

const open = ref(false);
const collapsed = ref(false);
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
	open.value = false;
}
</script>
