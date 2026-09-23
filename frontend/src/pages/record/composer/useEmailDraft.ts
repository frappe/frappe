// The email writer's draft: the headers, body and attachments, saved into the store as they change.
import { ref, watch } from "vue";
import type { Recipient, UploadedFile } from "@framework/ui/Composer";
import type { UploadTransport } from "@framework/ui/FileUpload";
import type { MediaUploadProgress, UploadedMedia } from "frappe-ui/editor";
import { saveComposerDraft } from "@/shell/composer";
import { EMAIL_WRITER, readEmailDraft, type EmailDraft } from "./emailDraft";
import { uploadCommentFile } from "./commentUpload";
import { asAttachment } from "./useCommentDraft";

// The editor writes an empty string only on reset, so the model starts from an empty paragraph.
const EMPTY_BODY = "<p></p>";

type UploadOptions = {
	signal?: AbortSignal;
	onProgress?: (progress: MediaUploadProgress) => void;
};

/** `fresh` is what Discard leaves; `transport` hangs each upload on the record, else on nothing. */
export function useEmailDraft(
	doctype: string,
	docname: string,
	fresh: () => EmailDraft,
	transport?: UploadTransport
) {
	const stored = readEmailDraft(doctype, docname);
	const from = ref(stored.from);
	const to = ref(asRecipients(stored.to));
	const cc = ref(asRecipients(stored.cc));
	const bcc = ref(asRecipients(stored.bcc));
	const subject = ref(stored.subject);
	const content = ref(stored.content || EMPTY_BODY);
	const attachments = ref<UploadedFile[]>([...stored.attachments]);
	const seed = [...stored.attachments];
	let inReplyTo = stored.inReplyTo;
	let resets = 0;

	watch([from, to, cc, bcc, subject, content, attachments], save, { deep: true });
	watch(content, (next) => next === "" && reset(), { flush: "sync" });

	// The editor passes options for inline media; the attach button calls with the file alone.
	async function upload(file: File, options?: UploadOptions): Promise<UploadedMedia> {
		const started = resets;
		const media = await uploadCommentFile(file, options, transport);
		// A reset during the upload dropped the file from the editor, so the draft drops it too.
		if (!options && started === resets)
			attachments.value = [...attachments.value, asAttachment(media)];
		return media;
	}

	// Discard leaves what a plain open of the writer shows; the chosen sender stays.
	function reset() {
		resets++;
		const start = fresh();
		to.value = asRecipients(start.to);
		cc.value = asRecipients(start.cc);
		bcc.value = asRecipients(start.bcc);
		subject.value = start.subject;
		inReplyTo = "";
		attachments.value = [];
		content.value = EMPTY_BODY;
	}

	function forget(file: UploadedFile) {
		attachments.value = attachments.value.filter((one) => one.name !== file.name);
	}

	function draft(): EmailDraft {
		return {
			from: from.value,
			to: addresses(to.value),
			cc: addresses(cc.value),
			bcc: addresses(bcc.value),
			subject: subject.value,
			content: content.value,
			attachments: attachments.value,
			inReplyTo,
		};
	}

	function save() {
		saveComposerDraft(doctype, docname, EMAIL_WRITER, draft());
	}

	return { from, to, cc, bcc, subject, content, seed, upload, forget, draft };
}

function asRecipients(list: string[]): Recipient[] {
	return list.map((email) => ({ email }));
}

function addresses(list: Recipient[]) {
	return list.map((recipient) => recipient.email);
}
