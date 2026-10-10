import { t } from "./translate";
import type { DataImportDoc, DataImportProgress } from "./types";

export function progressPercent(progress: DataImportProgress): number {
  if (!progress.total) return 0;
  const percent = Math.floor((progress.current * 100) / progress.total);
  return Math.max(0, Math.min(100, percent));
}

export function etaMessage(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  if (seconds < 60) return t("About {0} seconds remaining", [seconds]);
  if (minutes === 1) return t("About {0} minute remaining", [minutes]);
  return t("About {0} minutes remaining", [minutes]);
}

/** Before the first progress event the counts are still zero. */
export function hasProgressCounts(progress: DataImportProgress): boolean {
  return !!(progress.current && progress.total);
}

/** The line under the progress bar in Desk's form dashboard. */
export function progressMessage(
  doc: DataImportDoc,
  progress: DataImportProgress
): string {
  if (!hasProgressCounts(progress)) return notStartedMessage(doc);
  const args = [progress.current, progress.total, etaMessage(progress.eta)];
  if (progress.skipping) return t("Skipping {0} of {1}, {2}", args);
  if (doc.import_type === "Update Existing Records")
    return t("Updating {0} of {1}, {2}", args);
  if (doc.import_type === "Insert or Update Records")
    return t("Importing or updating {0} of {1}, {2}", args);
  return t("Importing {0} of {1}, {2}", args);
}

// "Pending" while running means Import was pressed here and the worker hasn't
// picked the job up; "In Progress" means the import was opened mid-run.
export function notStartedMessage(doc: DataImportDoc): string {
  return doc.status === "Pending"
    ? t("Starting import...")
    : t("Import is running. Progress updates will appear shortly.");
}
