/** Default upload transport: the queue's args in the shape the v2 document routes take. */
import { attachFile, uploadFile } from "../../api";
import type { UploadFields } from "../../api";
import type { UploadArgs, UploadTransport } from "./types";

/** Default Frappe folder for detached uploads (FormLayout fields lack a docname). */
const DEFAULT_FOLDER = "Home/Attachments";

export function createFrappeTransport(): UploadTransport {
  return async (file, args, ctx) => {
    const fields = fieldsOf(args);
    const options = { onProgress: ctx.onProgress, signal: ctx.signal, chunkSize: ctx.chunkSize };
    const attachTo = args.attachTo;
    if (!attachTo) {
      const { data } = await uploadFile(file, fields, options);
      return { file_url: data.file_url, name: data.name };
    }
    // The document route answers with the refreshed part and names the row it just made.
    const { data } = await attachFile(attachTo.doctype, attachTo.docname, file, fields, options);
    const uploaded = data.attachments.find((row) => row.name === data.file);
    if (!uploaded) throw new Error("Upload completed but no file URL was returned");
    return { file_url: uploaded.file_url, name: uploaded.name };
  };
}

/** The shared default instance used when no transport is injected. */
export const defaultTransport: UploadTransport = createFrappeTransport();

function fieldsOf(args: UploadArgs): UploadFields {
  return {
    is_private: args.isPrivate ? 1 : 0,
    folder: args.folder || DEFAULT_FOLDER,
    fieldname: args.attachTo?.fieldname,
    optimize: args.optimize ? 1 : undefined,
    max_width: args.optimize ? args.maxWidth : undefined,
    max_height: args.optimize ? args.maxHeight : undefined,
  };
}
