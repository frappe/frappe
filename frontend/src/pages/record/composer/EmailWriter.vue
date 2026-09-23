<!-- The built-in `email` writer: the header and editor, loaded on first open, over the record's draft. -->
<template>
	<div class="flex min-h-0 flex-1 flex-col" data-email-writer>
		<EmailComposer
			ref="composer"
			v-model="content"
			v-model:from="from"
			v-model:to="to"
			v-model:cc="cc"
			v-model:bcc="bcc"
			v-model:subject="subject"
			v-model:quoted="quoted"
			class="min-h-0 flex-1"
			:placeholder="__('Write an email…')"
			:submitLabel="__('Send')"
			:uploadFunction="upload"
			:submitting="sent"
			:disabled="choice.blocked"
			:showFrom="choice.senders.length > 1"
			:senders="senders"
			:searchRecipients="searchRecipients"
			showSubject
			fill
			@submit="send"
			@remove-attachment="forget"
			@discard="discard"
		>
			<template #actions="{ addAttachment }">
				<AttachmentSeed :files="seed" :add="addAttachment" />
			</template>
			<template v-if="choice.blocked" #footer>
				<p class="px-3 pb-2 text-sm text-ink-gray-6" data-email-no-sender>
					{{ __("No outgoing email account") }}
				</p>
			</template>
		</EmailComposer>
	</div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, inject, ref, watch } from "vue";
import type { SessionUser } from "@framework/ui/api";
import type { EmailPayload } from "@framework/ui/Composer";
import type { RecordPageController } from "@/recordPage";
import { __ } from "@/i18n";
import { RecordFeedsKey } from "../feed/recordFeeds";
import AttachmentSeed from "./AttachmentSeed";
import { postEmail } from "./emailPost";
import { freshEmail } from "./emailSeed";
import { chooseSender, loadSenders, searchRecipients, type SenderChoice } from "./emailSenders";
import { useEmailDraft } from "./useEmailDraft";

const EmailComposer = defineAsyncComponent(() =>
	import("@framework/ui/Composer").then((module) => module.EmailComposer)
);

const props = defineProps<{ controller: RecordPageController; user: SessionUser }>();

const feeds = inject(RecordFeedsKey, null);
const { from, to, cc, bcc, subject, content, quoted, seed, upload, forget, discard, draft } =
	useEmailDraft(
		props.controller.page.doctype,
		props.controller.page.docname,
		() => freshEmail(props.controller.page),
		recordTransport()
	);
const composer = ref<{ focus: () => void } | null>(null);
// A writer posts once; the band closes it, and a reopen draws a new one.
const sent = ref(false);
// Until the senders are read, nothing is blocked and the draft's own sender stands.
const choice = ref<SenderChoice>({ senders: [], from: from.value, blocked: false });
const ready = settleSenders();
const senders = computed(() => choice.value.senders.map((email) => ({ email })));

watch(composer, (editor) => editor?.focus());

// As in desk v1, a reader who may write the record attaches onto it, and the Files tab shows it.
function recordTransport() {
	const { doctype, docname, perms } = props.controller.page;
	return perms.write && feeds ? feeds.uploadTransport(doctype, docname) : undefined;
}

async function settleSenders() {
	try {
		choice.value = chooseSender(await loadSenders(), props.user.email, from.value);
		from.value = choice.value.from;
	} catch {
		// Unread, the server picks the sender when the email goes.
	}
}

async function send(payload: EmailPayload) {
	if (sent.value) return;
	sent.value = true;
	// Taken before the wait, so nothing done to the writer meanwhile changes what goes.
	const headers = draft();
	await ready;
	if (choice.value.blocked) {
		sent.value = false;
		return;
	}
	const author = {
		name: props.user.name,
		email: props.user.email,
		fullname: props.user.full_name,
		image: props.user.user_image ?? undefined,
	};
	// The editor's body carries the quote; the draft keeps them apart for a failure to restore.
	const outgoing = { ...headers, from: from.value, attachments: [...payload.attachments] };
	void postEmail(props.controller, author, outgoing, payload.body);
}
</script>
