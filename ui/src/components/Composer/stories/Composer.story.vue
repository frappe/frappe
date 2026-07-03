<template>
	<div class="mx-auto max-w-4xl p-6">
		<!-- ── Intro ────────────────────────────────────────────────────────── -->
		<h3 class="mb-1 text-xl-semibold text-ink-gray-9">Composer</h3>
		<p class="mb-6 text-p-sm text-ink-gray-6">
			A message composer assembled from compound parts that share state through an injected
			context. <code>Composer</code> owns the state (<code>v-model:open</code>,
			<code>v-model:channel</code>, <code>v-model:mode</code>);
			<code>ComposerTrigger</code> is the collapsed bar; <code>ComposerContent</code> is the
			floating/docked window; <code>ComposerChannel</code> associates content with a channel
			value (and a tab when several are present). <code>EmailComposer</code> and
			<code>CommentComposer</code> are ready-made channel content — they also render inline,
			standalone, when used without a window. Everything is transport-agnostic:
			<code>submit</code> hands back a payload and the host performs the send.
		</p>

		<!-- ── Live controls (drive the flagship example in §1) ─────────────── -->
		<section class="mb-6 rounded-lg border border-outline-gray-2 p-4">
			<div class="mb-3 text-sm-medium text-ink-gray-7">Controls</div>

			<div class="flex flex-wrap items-center gap-x-8 gap-y-4">
				<!-- Window state + chrome -->
				<div class="flex flex-wrap items-center gap-x-5 gap-y-2">
					<Switch v-model="open" label="open" size="sm" />
					<Switch v-model="minimizable" label="minimizable" size="sm" />
					<Switch v-model="floatable" label="floatable" size="sm" />
					<div class="flex items-center gap-2">
						<span class="text-p-sm text-ink-gray-6">mode</span>
						<Select v-model="mode" :options="modeOptions" />
					</div>
				</div>

				<!-- Email rows offered -->
				<div class="flex items-center gap-3">
					<span class="text-p-sm text-ink-gray-6">fields</span>
					<Checkbox v-model="fieldSubject" label="subject" />
					<Checkbox v-model="fieldCc" label="cc" />
					<Checkbox v-model="fieldBcc" label="bcc" />
				</div>
			</div>

			<!-- Imperative handle (exposed focus / reset / submit) + reply seeding -->
			<div
				class="mt-4 flex flex-wrap items-center gap-2 border-t border-outline-gray-1 pt-4"
			>
				<span class="mr-1 text-p-sm text-ink-gray-6">actions</span>
				<Button label="Focus" @click="focusActive" />
				<Button label="Reset" @click="resetActive" />
				<Button label="Submit" @click="submitActive" />
				<Button label="Seed quoted reply" @click="seedReply" />
				<span class="ml-auto text-p-sm text-ink-gray-5">
					open: <b>{{ open }}</b> · channel: <b>{{ channel }}</b> · mode:
					<b>{{ mode }}</b>
				</span>
			</div>
		</section>

		<!-- ── §1 Flagship: configurable two-channel window ─────────────────── -->
		<section class="mb-8">
			<div class="mb-2 text-sm-medium text-ink-gray-7">
				Two-channel window — recipients, subject, quoted reply, @-mentions, attachments,
				and a custom From picker, all driven by the controls above
			</div>
			<Composer
				v-model:open="open"
				v-model:channel="channel"
				v-model:mode="mode"
				:minimizable="minimizable"
			>
				<ComposerTrigger placeholder="Write a reply…" />
				<ComposerContent :floatable="floatable">
					<ComposerChannel value="email" label="Email">
						<EmailComposer
							ref="emailRef"
							v-model="emailBody"
							v-model:recipients="recipients"
							v-model:subject="subject"
							v-model:quoted="quoted"
							:fields="fields"
							:search-recipients="searchRecipients"
							:upload-function="mockUpload"
							submit-label="Send"
							placeholder="Write a reply…"
							@submit="(p) => log('email:submit', p)"
							@remove-attachment="(f) => log('email:remove-attachment', f)"
						>
							<!-- Host-supplied sender picker, injected above the recipient rows. -->
							<template #from>
								<div class="flex items-center gap-2 py-1.5">
									<span class="text-p-sm text-ink-gray-5">From</span>
									<Select
										class="relative !bottom-0.5"
										v-model="fromEmail"
										:options="identities"
									/>
								</div>
							</template>
						</EmailComposer>
					</ComposerChannel>

					<ComposerChannel value="comment" label="Comment">
						<CommentComposer
							ref="commentRef"
							v-model="commentBody"
							:mentions="mentions"
							:upload-function="mockUpload"
							placeholder="Leave an internal note — type @ to mention…"
							@submit="(p) => log('comment:submit', p)"
							@remove-attachment="(f) => log('comment:remove-attachment', f)"
						/>
					</ComposerChannel>
				</ComposerContent>
			</Composer>
			<pre
				class="mt-3 overflow-auto rounded-lg bg-surface-gray-2 p-3 text-xs text-ink-gray-8"
			><code>{{ flagshipCode }}</code></pre>
		</section>

		<!-- ── §2 Single channel — no switcher, header title falls back to label -->
		<section class="mb-8">
			<div class="mb-2 text-sm-medium text-ink-gray-7">
				Single channel — with only one <code>ComposerChannel</code> the switcher tabs
				disappear and the header shows the channel's label
			</div>
			<Composer>
				<ComposerTrigger placeholder="Add an internal note…" />
				<ComposerContent>
					<ComposerChannel value="comment" label="Note">
						<CommentComposer
							:mentions="mentions"
							:upload-function="mockUpload"
							placeholder="Type @ to mention a teammate…"
							@submit="(p) => log('note:submit', p)"
						/>
					</ComposerChannel>
				</ComposerContent>
			</Composer>
			<pre
				class="mt-3 overflow-auto rounded-lg bg-surface-gray-2 p-3 text-xs text-ink-gray-8"
			><code>{{ singleChannelCode }}</code></pre>
		</section>

		<!-- ── §3 Inline — content without a window ──────────────────────────── -->
		<section class="mb-8">
			<div class="mb-2 text-sm-medium text-ink-gray-7">
				Inline (no window) — <code>EmailComposer</code> / <code>CommentComposer</code>
				render on their own, always visible, no trigger or chrome
			</div>
			<div class="grid gap-4 md:grid-cols-2">
				<div class="rounded-md border border-outline-gray-2 bg-surface-base p-2">
					<EmailComposer
						v-model="inlineBody"
						v-model:recipients="inlineRecipients"
						:fields="['cc']"
						:search-recipients="searchRecipients"
						:upload-function="mockUpload"
						placeholder="Compose an email…"
						@submit="(p) => log('inline-email:submit', p)"
					/>
				</div>
				<div class="rounded-md border border-outline-gray-2 bg-surface-base p-2">
					<CommentComposer
						v-model="inlineComment"
						:mentions="mentions"
						:upload-function="mockUpload"
						placeholder="Write a comment…"
						@submit="(p) => log('inline-comment:submit', p)"
					/>
				</div>
			</div>
			<pre
				class="mt-3 overflow-auto rounded-lg bg-surface-gray-2 p-3 text-xs text-ink-gray-8"
			><code>{{ inlineCode }}</code></pre>
		</section>

		<!-- ── §4 Overridden window controls (#header-actions) ──────────────── -->
		<section class="mb-8">
			<div class="mb-2 text-sm-medium text-ink-gray-7">
				Custom window controls — the <code>#header-actions</code> slot replaces the default
				expand/minimize buttons while still driving real window behavior
			</div>
			<Composer>
				<ComposerTrigger placeholder="Reply…" />
				<ComposerContent>
					<template #header-actions="{ expand, minimize, floating }">
						<Button
							variant="ghost"
							:label="floating ? 'Dock' : 'Pop out'"
							@click="expand"
						/>
						<Button variant="ghost" label="Done" @click="minimize" />
					</template>
					<ComposerChannel value="comment" label="Comment">
						<CommentComposer
							:mentions="mentions"
							placeholder="Custom header controls…"
							@submit="(p) => log('custom-header:submit', p)"
						/>
					</ComposerChannel>
				</ComposerContent>
			</Composer>
			<pre
				class="mt-3 overflow-auto rounded-lg bg-surface-gray-2 p-3 text-xs text-ink-gray-8"
			><code>{{ headerActionsCode }}</code></pre>
		</section>

		<!-- ── §5 Custom trigger bar (default slot of ComposerTrigger) ──────── -->
		<section class="mb-8">
			<div class="mb-2 text-sm-medium text-ink-gray-7">
				Custom collapsed bar — <code>ComposerTrigger</code>'s default slot is scoped with
				the active channel's <code>preview</code>, so hosts can supply their own avatar and
				copy
			</div>
			<Composer>
				<ComposerTrigger v-slot="{ preview }">
					<Avatar size="sm" label="Ada Lovelace" class="shrink-0" />
					<span class="min-w-0 max-w-[30%] truncate text-base text-ink-gray-5">
						{{ preview || "Reply as Ada…" }}
					</span>
				</ComposerTrigger>
				<ComposerContent>
					<ComposerChannel value="comment" label="Comment">
						<CommentComposer
							:mentions="mentions"
							placeholder="Custom trigger avatar + preview…"
							@submit="(p) => log('custom-trigger:submit', p)"
						/>
					</ComposerChannel>
				</ComposerContent>
			</Composer>
			<pre
				class="mt-3 overflow-auto rounded-lg bg-surface-gray-2 p-3 text-xs text-ink-gray-8"
			><code>{{ customTriggerCode }}</code></pre>
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
import { Avatar, Button, Checkbox, Select, Switch } from "frappe-ui";
import { type WindowMode } from "frappe-ui/experimental";
import {
	CommentComposer,
	Composer,
	ComposerChannel,
	ComposerContent,
	ComposerTrigger,
	EmailComposer,
} from "../index";
import type {
	CommentPayload,
	EmailPayload,
	Field,
	MentionOption,
	Recipient,
	Recipients,
	UploadedFile,
	UploadFunction,
} from "../types";

// ── Window controls (bound to the flagship composer in §1) ─────────────────
const open = ref(false);
const minimizable = ref(true);
const floatable = ref(true);
const mode = ref<WindowMode>("docked");
const modeOptions: WindowMode[] = ["docked", "floating", "minimized"];

// ── Which optional email rows the flagship offers ──────────────────────────
const fieldSubject = ref(true);
const fieldCc = ref(true);
const fieldBcc = ref(false);
const fields = computed<Field[]>(() =>
	(
		[
			["subject", fieldSubject.value],
			["cc", fieldCc.value],
			["bcc", fieldBcc.value],
		] as const
	)
		.filter(([, on]) => on)
		.map(([name]) => name)
);

// ── Flagship draft state (host-owned via v-model, survives channel switches) ─
const channel = ref("email");
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

// Component refs expose { editor, focus, reset, submit } for imperative control.
const emailRef = ref<InstanceType<typeof EmailComposer> | null>(null);
const commentRef = ref<InstanceType<typeof CommentComposer> | null>(null);
const activeComposer = computed(() =>
	channel.value === "comment" ? commentRef.value : emailRef.value
);
function focusActive() {
	activeComposer.value?.focus();
}
function resetActive() {
	activeComposer.value?.reset();
}
function submitActive() {
	activeComposer.value?.submit();
}
// Drop a quoted message into the email channel to pre-fill a reply.
function seedReply() {
	channel.value = "email";
	quoted.value = "<p>On Tue, Grace wrote:</p><p>Can we ship the composer this week?</p>";
	open.value = true;
}

// ── Host-supplied sender picker for the #from slot ─────────────────────────
const identities = ["support@example.com", "sales@example.com"];
const fromEmail = ref(identities[0]);

// ── Focused-example state ──────────────────────────────────────────────────
const inlineBody = ref("");
const inlineComment = ref("");
const inlineRecipients = ref<Recipients>({ to: [], cc: [], bcc: [] });

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

// @-mention options for comment channels; the editor filters them on "@".
const mentions: MentionOption[] = [
	{ label: "Grace Hopper", value: "grace@example.com" },
	{ label: "Ada Lovelace", value: "ada@example.com" },
	{ label: "Alan Turing", value: "alan@example.com" },
];

// ── Code examples shown under each section ──────────────────────────────────
// Representative usage, not a literal dump of this story's own wiring (which
// carries story-only bits like the event log and live-controls binding).
const flagshipCode = `<Composer v-model:open="open" v-model:channel="channel">
  <ComposerTrigger placeholder="Write a reply…" />
  <ComposerContent>
    <ComposerChannel value="email" label="Email">
      <EmailComposer
        v-model="body"
        v-model:recipients="recipients"
        v-model:subject="subject"
        v-model:quoted="quoted"
        :fields="['subject', 'cc']"
        :search-recipients="searchRecipients"
        :upload-function="uploadFile"
        @submit="onEmailSubmit"
      >
        <template #from>
          <SenderPicker v-model="fromEmail" :options="identities" />
        </template>
      </EmailComposer>
    </ComposerChannel>

    <ComposerChannel value="comment" label="Comment">
      <CommentComposer
        v-model="commentBody"
        :mentions="mentions"
        @submit="onCommentSubmit"
      />
    </ComposerChannel>
  </ComposerContent>
</Composer>`;

const singleChannelCode = `<Composer>
  <ComposerTrigger placeholder="Add an internal note…" />
  <ComposerContent>
    <ComposerChannel value="comment" label="Note">
      <CommentComposer :mentions="mentions" @submit="onSubmit" />
    </ComposerChannel>
  </ComposerContent>
</Composer>`;

const inlineCode = `<!-- No Composer / ComposerContent — renders in normal document flow. -->
<EmailComposer
  v-model="body"
  v-model:recipients="recipients"
  :fields="['cc']"
  :search-recipients="searchRecipients"
  @submit="onSubmit"
/>

<CommentComposer v-model="commentBody" :mentions="mentions" @submit="onSubmit" />`;

const headerActionsCode = `<Composer>
  <ComposerTrigger placeholder="Reply…" />
  <ComposerContent>
    <template #header-actions="{ expand, minimize, floating }">
      <Button :label="floating ? 'Dock' : 'Pop out'" @click="expand" />
      <Button label="Done" @click="minimize" />
    </template>
    <ComposerChannel value="comment" label="Comment">
      <CommentComposer :mentions="mentions" @submit="onSubmit" />
    </ComposerChannel>
  </ComposerContent>
</Composer>`;

const customTriggerCode = `<Composer>
  <ComposerTrigger v-slot="{ preview }">
    <Avatar size="sm" label="Ada Lovelace" />
    <span class="min-w-0 max-w-[30%] truncate">{{ preview || 'Reply as Ada…' }}</span>
  </ComposerTrigger>
  <ComposerContent>
    <ComposerChannel value="comment" label="Comment">
      <CommentComposer :mentions="mentions" @submit="onSubmit" />
    </ComposerChannel>
  </ComposerContent>
</Composer>`;

// ── Event log ──────────────────────────────────────────────────────────────
const events = ref<string[]>([]);
function log(name: string, payload?: EmailPayload | CommentPayload | UploadedFile) {
	const time = new Date().toLocaleTimeString();
	events.value.unshift(`[${time}] ${name}${payload ? " " + JSON.stringify(payload) : ""}`);
}
</script>
