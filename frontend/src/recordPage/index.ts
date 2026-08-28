// The record-page engine's one entry, so a call site imports from `@/recordPage` and
// nothing deeper.
//
// The engine lives in the shell rather than in `@framework/ui` because it is desk
// layer, not generic layer: `@framework/ui` holds self-contained components an app may
// use however it likes, while this is one opinionated record-page runtime that speaks
// doctype, `page.save()` and Page Script. It CONSUMES the generic layer -- FormLayout,
// Fields, useDocPermissions -- which is what places it on this side of the boundary.
//
// A contributed `record.js` imports nothing at all: its default export IS the
// registration, and the shell's contribution registry is what reaches this file.
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
