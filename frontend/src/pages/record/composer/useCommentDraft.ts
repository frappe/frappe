// The comment writer's draft: the editor's content and attachments, saved into the store as they change.
import { ref, watch } from "vue";
import type { UploadedFile } from "@framework/ui/Composer";
import type { MediaUploadProgress, UploadedMedia } from "frappe-ui/editor";
import { saveComposerDraft } from "@/shell/composer";
import { COMMENT_WRITER, readCommentDraft } from "./commentDraft";
import { uploadCommentFile } from "./commentUpload";

// The editor writes an empty string only on reset, so the model starts from an empty paragraph.
const EMPTY_BODY = "<p></p>";

type UploadOptions = {
	signal?: AbortSignal;
	onProgress?: (progress: MediaUploadProgress) => void;
};

export function useCommentDraft(doctype: string, docname: string) {
	const stored = readCommentDraft(doctype, docname);
	const content = ref(stored.content || EMPTY_BODY);
	const attachments = ref<UploadedFile[]>([...stored.attachments]);
	const seed = [...stored.attachments];
	let resets = 0;

	watch([content, attachments], save, { deep: true });
	watch(content, (next) => next === "" && reset(), { flush: "sync" });

	// The editor passes options for inline media; the attach button calls with the file alone.
	async function upload(file: File, options?: UploadOptions): Promise<UploadedMedia> {
		const started = resets;
		const media = await uploadCommentFile(file, options);
		// A reset during the upload dropped the file from the editor, so the draft drops it too.
		if (!options && started === resets)
			attachments.value = [...attachments.value, asAttachment(media)];
		return media;
	}

	function reset() {
		resets++;
		attachments.value = [];
		content.value = EMPTY_BODY;
	}

	function forget(file: UploadedFile) {
		attachments.value = attachments.value.filter((one) => one.name !== file.name);
	}

	function save() {
		saveComposerDraft(doctype, docname, COMMENT_WRITER, {
			content: content.value,
			attachments: attachments.value,
		});
	}

	return { content, attachments, seed, upload, forget };
}

function asAttachment(media: UploadedMedia): UploadedFile {
	return {
		name: media.name ?? media.file_url,
		file_name: media.file_name ?? "",
		file_url: media.file_url,
		file_type: media.file_type ?? "",
		file_size: media.file_size,
	};
}
