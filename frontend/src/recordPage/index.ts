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

export { createRecordPage, SAVE_VETO } from "./createRecordPage";
export { createCommitChannel } from "./commitChannel";
export type { RecordCommitChannel } from "./commitChannel";
export { errorMessage } from "./errorMessage";
export { setIconSource } from "./iconClasses";
export type { IconSource } from "./iconClasses";
export { loadClientScripts, reloadClientScripts } from "./clientScripts";
export type { RecordPageController } from "./createRecordPage";

export type { AuthoredHandlers, Handler, RecordPageHandlers } from "./types";

export { isEmptyHeader, projectHeader, zoneOf } from "./headerRenderings";
export { projectFrame } from "./frame";
export type { FrameProjection } from "./frame";
export { columnBounds, dragOutcome, isDrawn, projectBody, STRIP_WIDTH } from "./body";
export type { BodyColumn, ColumnBounds, EdgeSide, Remembered } from "./body";
export { setDrawnProps } from "./drawnProps";
export type { DrawnProps } from "./drawnProps";
export type {
  HeaderBand,
  HeaderControl,
  HeaderNode,
  HeaderProjection,
} from "./headerRenderings";
export { formItems, joinForm } from "./formJoin";
export type {
  BodyItem,
  FormItem,
  FrameItem,
  HeaderItem,
  PanelSectionItem,
  PageForm,
  PanelSectionsApi,
  QuickAction,
  RecordPageApi,
} from "./types";

export { useFormLayout, resetFormLayouts } from "./formLayoutSource/useFormLayout";
export type { FormLayoutType } from "./formLayoutSource/types";
export { sectionName } from "./formLayoutSource/sectionName";
