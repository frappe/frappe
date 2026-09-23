// The comment writer's uploads: private and unattached until the new comment claims them.
import { defaultTransport } from "@framework/ui/FileUpload";
import type { MediaUploadProgress, UploadedMedia } from "frappe-ui/editor";

/** Uploads one file as the editor's attach button and inline media expect. */
export async function uploadCommentFile(
	file: File,
	options: {
		signal?: AbortSignal;
		onProgress?: (progress: MediaUploadProgress) => void;
	} = {}
): Promise<UploadedMedia> {
	const signal = options.signal ?? new AbortController().signal;
	const onProgress = (loaded: number, total: number) =>
		options.onProgress?.({
			loaded,
			total,
			percent: total ? Math.round((loaded / total) * 100) : 0,
		});
	const uploaded = await defaultTransport(file, { isPrivate: true }, { signal, onProgress });
	return {
		name: uploaded.name,
		file_url: uploaded.file_url,
		file_name: file.name,
		file_type: file.type,
		file_size: file.size,
		is_private: 1,
	};
}
