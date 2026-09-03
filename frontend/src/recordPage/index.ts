// The record-page engine's one entry, so a call site imports from `@/recordPage` and nothing deeper.
export {
  ALL_DOCTYPES,
  registerRecordPage,
  registrationsFor,
  resetRegistry,
  unregisterSource,
} from "./registry";
export type { Registration } from "./registry";

export {
  HOST_SOURCE,
  registeringSource,
  runningSource,
  withRegisteringSource,
  withRunningSource,
} from "./context";

export { createRecordPage } from "./createRecordPage";
export type { RecordPageController } from "./createRecordPage";

export type { AuthoredHandlers, Handler, RecordPageHandlers } from "./types";
