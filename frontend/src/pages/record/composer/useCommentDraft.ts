// The comment writer's draft: the editor's content and attachments, saved into the store as they change.
import { ref, watch } from "vue";
import type { UploadedFile } from "@framework/ui/Composer";
import type { MediaUploadProgress, UploadedMedia } from "frappe-ui/editor";
import { composerDraft, saveComposerDraft } from "@/shell/composer";
import { COMMENT_WRITER, type CommentDraft } from "./commentPost";
import { uploadCommentFile } from "./commentUpload";

type UploadOptions = {
	signal?: AbortSignal;
	onProgress?: (progress: MediaUploadProgress) => void;
};

export function useCommentDraft(doctype: string, docname: string) {
	const stored = readDraft(doctype, docname);
	const content = ref(stored.content);
	const attachments = ref<UploadedFile[]>([...stored.attachments]);
	const seed = [...stored.attachments];

	watch([content, attachments], save, { deep: true });
	// Only the editor's reset writes an empty string; an emptied editor holds `<p></p>`.
	watch(content, (next) => next === "" && (attachments.value = []));

	// The editor passes options for inline media; the attach button calls with the file alone.
	async function upload(file: File, options?: UploadOptions): Promise<UploadedMedia> {
		const media = await uploadCommentFile(file, options);
		if (!options) attachments.value = [...attachments.value, asAttachment(media)];
		return media;
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

function readDraft(doctype: string, docname: string): CommentDraft {
	const draft = composerDraft(doctype, docname, COMMENT_WRITER) ?? {};
	return {
		content: typeof draft.content === "string" ? draft.content : "",
		attachments: Array.isArray(draft.attachments) ? (draft.attachments as UploadedFile[]) : [],
	};
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
