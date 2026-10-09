import { isImportComplete, parseJson } from "./dataImport";
import type { DataImportDoc } from "./types";

export const CONFIG = 0;
export const PREVIEW = 1;
export const FIX_ISSUES = 2;
export const IMPORT = 3;

export interface StepState {
  isNew: boolean;
  hasImportFile: boolean;
  importStarted: boolean;
}

/** The step an import opens on, from its saved state. */
export function landingStep(doc: DataImportDoc): number {
  if (doc.status && doc.status !== "Pending") return IMPORT;
  if (!(doc.import_file || doc.google_sheets_url)) return CONFIG;
  const hasIssues =
    doc.skipped_rows.length > 0 ||
    doc.value_mappings.length > 0 ||
    parseJson<unknown[]>(doc.template_warnings, []).length > 0;
  return hasIssues ? FIX_ISSUES : PREVIEW;
}

/** Whether `step` can be opened from `current`; earlier steps always can. */
export function canGoToStep(
  step: number,
  current: number,
  doc: DataImportDoc,
  state: StepState
): boolean {
  if (step <= current) return true;
  const saved = !state.isNew && state.hasImportFile;
  if (step === PREVIEW)
    return !!(doc.reference_doctype && doc.import_type) && saved;
  if (step === FIX_ISSUES) return saved;
  if (step === IMPORT) return saved && state.importStarted;
  return false;
}

/** Earlier steps count as done once the import starts, the last once it finishes. */
export function isStepCompleted(
  step: number,
  current: number,
  doc: DataImportDoc,
  state: StepState
): boolean {
  if (step < current) return true;
  if (step < IMPORT) return state.importStarted;
  return isImportComplete(doc.status);
}
