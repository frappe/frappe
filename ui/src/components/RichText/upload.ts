/** The editor's upload over a `FileUpload` transport: private, detached unless `args` attach it. */
import type { MediaUploadRequestOptions, UploadedMedia } from "frappe-ui/editor";
import { defaultTransport } from "../FileUpload/useFileUpload";
import type { UploadArgs, UploadTransport } from "../FileUpload/types";

export async function uploadMedia(
  file: File,
  options: MediaUploadRequestOptions = {},
  args: UploadArgs = { isPrivate: true },
  transport: UploadTransport = defaultTransport
): Promise<UploadedMedia> {
  const signal = options.signal ?? new AbortController().signal;
  const onProgress = (loaded: number, total: number) =>
    options.onProgress?.({
      loaded,
      total,
      percent: total ? Math.round((loaded / total) * 100) : 0,
    });
  const uploaded = await transport(file, args, { signal, onProgress });
  return {
    name: uploaded.name,
    file_url: uploaded.file_url,
    file_name: file.name,
    file_type: file.type,
    file_size: file.size,
    is_private: args.isPrivate ? 1 : 0,
  };
}
