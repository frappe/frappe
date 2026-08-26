// Everything under `src/experimental` reaches its callers through this one barrel, so a
// call site imports from "@framework/ui/experimental" and nothing deeper. See
// ./README.md on `feat/saved-view-sidebar` for what "experimental" promises (very little).
//
// This copy is deliberately NARROWER than the one on `feat/saved-view-sidebar`. Only the
// record-page engine has been cherry-picked onto desk-v2 so far — the shell needs it to
// render `/apps/<app>/<doctype>/<name>`. Navigation, SavedViews, PageScriptEditor,
// PanelLayout and IconPicker are still branch-only and are NOT re-exported here.
//
// Widen this file one subsystem at a time, as a ticket needs one. Re-exporting a module
// whose sources have not been cherry-picked will not fail here — it fails in the consuming
// app's vite build, which is a much worse place to find out.
export {
  ALL_DOCTYPES,
  registerRecordPage,
  registrationsFor,
  resetRegistry,
  unregisterSource,
} from "./RecordPage/registry";
export type { Registration } from "./RecordPage/registry";

export {
  HOST_SOURCE,
  registeringSource,
  runningSource,
  withRegisteringSource,
  withRunningSource,
} from "./RecordPage/context";

export { createRecordPage } from "./RecordPage/createRecordPage";
export type { RecordPageController } from "./RecordPage/createRecordPage";

export type {
  AuthoredHandlers,
  Handler,
  RecordPageHandlers,
} from "./RecordPage/types";
