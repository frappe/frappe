<template>
	<div class="mx-auto max-w-4xl p-6">
		<!-- ── Intro ────────────────────────────────────────────────────────── -->
		<h3 class="mb-1 text-xl-semibold text-ink-gray-9">Composers</h3>
		<p class="mb-6 text-p-sm text-ink-gray-6">
			Two standalone, inline message composers. <code>EmailComposer</code> stacks email
			header rows (From/Subject/To/Cc/Bcc, per <code>headerFields</code>) plus an optional
			quoted reply above the editor; <code>CommentComposer</code> is the editor alone, with
			@-mentions, for internal notes. Both are transport-agnostic — <code>submit</code> hands
			back a payload and the host performs the send, then calls the exposed
			<code>reset()</code>. They render in normal document flow: an Email/Comment tab
			switcher (§1) and a docked reply window (§2) are a few host lines, not library surface.
		</p>

		<!-- ── Live controls (drive the flagship in §1) ─────────────────────── -->
		<section class="mb-6 rounded-lg border border-outline-gray-2 p-4">
			<div class="mb-3 text-sm-medium text-ink-gray-7">Controls</div>

			<div class="flex flex-wrap items-center gap-x-8 gap-y-4">
				<!-- Which header rows are offered (untick all to drop the section) -->
				<div class="flex items-center gap-3">
					<span class="text-p-sm text-ink-gray-6">headerFields</span>
					<Checkbox v-model="fieldFrom" label="from" />
					<Checkbox v-model="fieldTo" label="to" />
					<Checkbox v-model="fieldSubject" label="subject" />
					<Checkbox v-model="fieldCc" label="cc" />
					<Checkbox v-model="fieldBcc" label="bcc" />
				</div>
			</div>

			<!-- Imperative handle (exposed focus / reset / submit) on the active tab -->
			<div
				class="mt-4 flex flex-wrap items-center gap-2 border-t border-outline-gray-1 pt-4"
			>
				<span class="mr-1 text-p-sm text-ink-gray-6">actions</span>
				<Button label="Focus" @click="activeComposer?.focus()" />
				<Button label="Reset" @click="activeComposer?.reset()" />
				<Button label="Submit" @click="activeComposer?.submit()" />
				<Button label="Seed quoted reply" @click="seedReply" />
				<span class="ml-auto text-p-sm text-ink-gray-5">
					channel: <b>{{ channel }}</b>
				</span>
			</div>
		</section>

		<!-- ── §1 Flagship: switchable Email / Comment composer ─────────────── -->
		<section class="mb-8">
			<div class="mb-2 text-sm-medium text-ink-gray-7">
				Switchable composer — Email and Comment share one area via
				<code>TabButtons</code>; each draft survives a tab switch because both stay mounted
				(<code>v-show</code>, not <code>v-if</code>)
			</div>
			<div class="rounded-md border border-outline-gray-2 bg-surface-base">
				<div class="border-b border-outline-gray-2 p-2">
					<TabButtons v-model="channel" :options="channelOptions" />
				</div>

				<!-- Email tab -->
				<div v-show="channel === 'email'" class="p-2">
					<EmailComposer
						ref="emailRef"
						v-model="emailBody"
						v-model:recipients="recipients"
						v-model:subject="subject"
						v-model:quoted="quoted"
						v-model:from="fromEmail"
						:header-fields="headerFields"
						:senders="senders"
						:search-recipients="searchRecipients"
						:upload-function="mockUpload"
						placeholder="Write a reply…"
						@submit="(payload) => log('email:submit', payload)"
						@remove-attachment="(file) => log('email:remove-attachment', file)"
					/>
				</div>

				<!-- Comment tab -->
				<div v-show="channel === 'comment'" class="p-2">
					<CommentComposer
						ref="commentRef"
						v-model="commentBody"
						:mentions="mentions"
						:upload-function="mockUpload"
						placeholder="Leave an internal note — type @ to mention…"
						@submit="(payload) => log('comment:submit', payload)"
						@remove-attachment="(file) => log('comment:remove-attachment', file)"
					/>
				</div>
			</div>
			<pre
				class="mt-3 overflow-auto rounded-lg bg-surface-gray-2 p-3 text-xs text-ink-gray-8"
			><code>{{ tabbedCode }}</code></pre>
		</section>

		<!-- ── §2 Windowed (host recipe) ────────────────────────────────────── -->
		<section class="mb-8">
			<div class="mb-2 text-sm-medium text-ink-gray-7">
				A docked reply window is the host's own <code>FloatingWindow</code> around an
				inline composer — the library stays out of the window business (FP1)
			</div>
			<pre
				class="overflow-auto rounded-lg bg-surface-gray-2 p-3 text-xs text-ink-gray-8"
			><code>{{ windowRecipe }}</code></pre>
		</section>

		<!-- ── §3 Custom addressing (host recipe) ───────────────────────────── -->
		<section class="mb-8">
			<div class="mb-2 text-sm-medium text-ink-gray-7">
				<code>#header</code> replaces the built-in header rows wholesale — provide it empty
				to render no header at all
			</div>
			<pre
				class="overflow-auto rounded-lg bg-surface-gray-2 p-3 text-xs text-ink-gray-8"
			><code>{{ headerRecipe }}</code></pre>
		</section>

		<!-- ── Event log ─────────────────────────────────────────────────────── -->
		<div class="text-sm-medium text-ink-gray-7">Events</div>
		<pre
			class="mt-2 max-h-64 overflow-auto rounded-lg bg-surface-gray-2 p-3 text-xs text-ink-gray-8"
			>{{
				events.length
					? events.join("\n")
					: "— interact above to see submit / attachment events —"
			}}</pre
		>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Button, Checkbox, TabButtons } from "frappe-ui";
import { CommentComposer, EmailComposer } from "../index";
import type {
	CommentPayload,
	EmailPayload,
	HeaderField,
	MentionOption,
	Recipient,
	Recipients,
	UploadedFile,
	UploadFunction,
} from "../types";

// ── Switcher: which composer the one area shows ────────────────────────────
const channel = ref("email");
const channelOptions = [
	{ label: "Email", value: "email" },
	{ label: "Comment", value: "comment" },
];

// ── Which header rows the composer offers ──────────────────────────────────
const fieldFrom = ref(true);
const fieldTo = ref(true);
const fieldSubject = ref(true);
const fieldCc = ref(true);
const fieldBcc = ref(false);
const headerFields = computed<HeaderField[]>(() =>
	(
		[
			["from", fieldFrom.value],
			["to", fieldTo.value],
			["subject", fieldSubject.value],
			["cc", fieldCc.value],
			["bcc", fieldBcc.value],
		] as const
	)
		.filter(([, on]) => on)
		.map(([name]) => name)
);

// ── Draft state (host-owned via v-model, survives tab switches) ────────────
const emailBody = ref("");
const commentBody = ref("");
const subject = ref("");
// Quoted reply HTML, shown as a collapsible block and appended back on send.
const quoted = ref<string | null>(null);
// Recipients are host-owned — seed a reply and observe edits.
const recipients = ref<Recipients>({
	to: [{ email: "grace@example.com", label: "Grace Hopper" }],
	cc: [],
	bcc: [],
});

// Each composer exposes { editor, focus, reset, submit }; drive the active tab.
const emailRef = ref<InstanceType<typeof EmailComposer> | null>(null);
const commentRef = ref<InstanceType<typeof CommentComposer> | null>(null);
const activeComposer = computed(() =>
	channel.value === "comment" ? commentRef.value : emailRef.value
);
// Drop a quoted message into the email channel to pre-fill a reply.
function seedReply() {
	channel.value = "email";
	quoted.value = "<p>On Tue, Grace wrote:</p><p>Can we ship the composer this week?</p>";
	emailRef.value?.focus();
}

// ── Sender identities for the built-in From row ────────────────────────────
const senders: Recipient[] = [
	{ label: "Support", email: "support@example.com" },
	{ label: "Sales", email: "sales@example.com" },
];
const fromEmail = ref(senders[0].email);

// ── Mocked transports (a real host wires these to its backend) ─────────────
// Attachment upload: fake latency, then a File-shaped result the chip renders.
const mockUpload: UploadFunction = async (file) => {
	await new Promise((resolve) => setTimeout(resolve, 600));
	return {
		name: `mock-${Date.now()}`,
		file_name: file.name,
		file_url: URL.createObjectURL(file),
		file_size: file.size,
		file_type: file.type,
	};
};

// Recipient search: the composer calls this (debounced) as the user types To/
// Cc/Bcc. Fake latency stands in for a contacts/users endpoint.
const directory: Recipient[] = [
	{ label: "Grace Hopper", email: "grace@example.com" },
	{ label: "Ada Lovelace", email: "ada@example.com" },
	{ label: "Alan Turing", email: "alan@example.com" },
	{ label: "Katherine Johnson", email: "katherine@example.com" },
];
function searchRecipients(query: string): Promise<Recipient[]> {
	const text = query.trim().toLowerCase();
	const matches = text
		? directory.filter(
				(person) =>
					person.label!.toLowerCase().includes(text) ||
					person.email.toLowerCase().includes(text)
		  )
		: directory;
	return new Promise((resolve) => setTimeout(() => resolve(matches), 300));
}

// @-mention options for the comment composer; the editor filters them on "@".
const mentions: MentionOption[] = [
	{ label: "Grace Hopper", value: "grace@example.com" },
	{ label: "Ada Lovelace", value: "ada@example.com" },
	{ label: "Alan Turing", value: "alan@example.com" },
];

// ── Code samples shown under the sections ──────────────────────────────────
const tabbedCode = `<TabButtons v-model="channel" :options="channelOptions" />

<div v-show="channel === 'email'">
  <EmailComposer
    v-model="emailBody"
    v-model:recipients="recipients"
    :search-recipients="searchRecipients"
    @submit="onSendEmail"
  />
</div>
<div v-show="channel === 'comment'">
  <CommentComposer v-model="commentBody" :mentions="mentions" @submit="onComment" />
</div>`;

const windowRecipe = `<FloatingWindow v-model:open="open">
  <EmailComposer v-model="body" v-model:recipients="recipients" @submit="onSend" />
</FloatingWindow>`;

const headerRecipe = `<!-- Custom addressing UI -->
<EmailComposer v-model="body" v-model:recipients="recipients" @submit="onSend">
  <template #header>
    <MyAddressBar v-model="recipients" />
  </template>
</EmailComposer>

<!-- No header at all — body-only reply, recipients seeded by the host -->
<EmailComposer v-model="body" v-model:recipients="recipients" @submit="onSend">
  <template #header />
</EmailComposer>`;

// ── Event log ──────────────────────────────────────────────────────────────
const events = ref<string[]>([]);
function log(name: string, payload?: EmailPayload | CommentPayload | UploadedFile) {
	const time = new Date().toLocaleTimeString();
	events.value.unshift(`[${time}] ${name}${payload ? " " + JSON.stringify(payload) : ""}`);
}
</script>
