// File-upload primitive: the reusable consumers + headless engine + source seam.
// A standalone subsystem (not a single widget) — the `Attach`/`Attach Image`/
// `Image` FormLayout fields wire `FileUploadDialog` through their registry, but
// everything here is exported so apps can build their own upload surfaces (e.g.
// an attachments panel) and register extra sources. Distinct from frappe-ui's
// single-file `FileUploader`.
export { default as FileUploadDialog } from "./FileUploadDialog.vue";
export { default as AttachmentsList } from "./AttachmentsList.vue";
export { default as UploadTray } from "./UploadTray.vue";
export { useUploader } from "./useUploader";
export type { Uploader, UseUploaderOptions } from "./useUploader";
export { createFrappeTransport, defaultTransport } from "./useFileUpload";
export { registerUploadSource, getUploadSources } from "./sources";
export type { UploadSource } from "./sources";
export {
  pushTrayBatch,
  removeTrayBatch,
  clearFinishedBatches,
  clearAllBatches,
  useTray,
} from "./uploadTray";
export type { TrayBatch } from "./uploadTray";
export type {
  UploadArgs,
  UploadTransport,
  Restrictions,
  UploadItem,
  UploadResult,
  ProgressMode,
} from "./types";
