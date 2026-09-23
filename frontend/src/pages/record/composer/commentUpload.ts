// The composer's uploads: private, and hung on nothing unless the caller passes a transport.
import { defaultTransport, type UploadTransport } from "@framework/ui/FileUpload";
import type { MediaUploadProgress, UploadedMedia } from "frappe-ui/editor";

/** Uploads one file as the editor's attach button and inline media expect. */
export async function uploadCommentFile(
	file: File,
	options: {
		signal?: AbortSignal;
		onProgress?: (progress: MediaUploadProgress) => void;
	} = {},
	transport: UploadTransport = defaultTransport
): Promise<UploadedMedia> {
	const signal = options.signal ?? new AbortController().signal;
	const onProgress = (loaded: number, total: number) =>
		options.onProgress?.({
			loaded,
			total,
			percent: total ? Math.round((loaded / total) * 100) : 0,
		});
	const uploaded = await transport(file, { isPrivate: true }, { signal, onProgress });
	return {
		name: uploaded.name,
		file_url: uploaded.file_url,
		file_name: file.name,
		file_type: file.type,
		file_size: file.size,
		is_private: 1,
	};
}
