// The composer's uploads: private, and hung on nothing unless the caller passes a transport.
import { defaultTransport, type UploadTransport } from "@framework/ui/FileUpload";
import { uploadMedia } from "@framework/ui/components/RichText/upload";
import type { MediaUploadRequestOptions, UploadedMedia } from "frappe-ui/editor";

/** Uploads one file as the editor's attach button and inline media expect. */
export function uploadCommentFile(
	file: File,
	options: MediaUploadRequestOptions = {},
	transport: UploadTransport = defaultTransport
): Promise<UploadedMedia> {
	return uploadMedia(file, options, { isPrivate: true }, transport);
}
