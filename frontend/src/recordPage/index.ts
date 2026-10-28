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
} from "@/pageEngine";

export { createRecordPage, SAVE_VETO } from "./createRecordPage";
export { createCommitChannel } from "./commitChannel";
export type { RecordCommitChannel } from "./commitChannel";
export { errorMessage } from "./errorMessage";
export { FieldErrors } from "./fieldErrors";
export { missingRequired } from "./requiredFields";
export { setAppPageScripts, setIconSource } from "@/pageEngine";
export type { IconSource } from "@/pageEngine";
export {
  clientScriptChanges,
  invalidateClientScripts,
  watchClientScripts,
} from "./clientScripts";
export { addFileScript, loadRecordScripts } from "./scriptLoader";
export { addPageFile } from "./pageScripts";
export { appPageScriptSource } from "./appPageScriptSource";
export type { RecordPageController } from "./createRecordPage";

export type { AuthoredHandlers, Handler, PostedRow, RecordPageHandlers } from "./types";

export { hidingDenied, isEmptyHeader, projectHeader, zoneOf } from "@/pageEngine";
export { projectFrame } from "@/pageEngine";
export type { FrameProjection } from "@/pageEngine";
export { columnBounds, dragOutcome, isDrawn, projectBody, STRIP_WIDTH } from "@/pageEngine";
export type { BodyColumn, ColumnBounds, EdgeSide, Remembered } from "@/pageEngine";
export { setDrawnProps } from "@/pageEngine";
export type { DrawnProps } from "@/pageEngine";
export type {
  HeaderBand,
  HeaderControl,
  HeaderNode,
  HeaderProjection,
} from "@/pageEngine";
export { formItems, joinForm } from "./formJoin";
export { COMPOSER_TABS, isComposerTab } from "./composer";
export type { ComposerHost, ComposerSurface } from "./composer";
export type {
  ActivityItem,
  ActivityRow,
  BodyItem,
  ComposerOpenOptions,
  ComposerWindow,
  FeedItem,
  FileRow,
  FormItem,
  FrameItem,
  HeaderItem,
  PanelSectionItem,
  PageForm,
  PanelSectionsApi,
  PageActivity,
  PageComposer,
  PageFiles,
  QuickAction,
  RecordPageApi,
  WriterItem,
} from "./types";

export { useFormLayout, resetFormLayouts } from "./formLayoutSource/useFormLayout";
export type { FormLayoutType } from "./formLayoutSource/types";
export { sectionName } from "./formLayoutSource/sectionName";
