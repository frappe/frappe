import type { CommitChannel } from "./types";

/**
 * A layout with no `CommitKey` provider drops every commit silently, which
 * reads as a script whose field handlers never fire. A form that genuinely has
 * no events provides `NO_COMMIT` to say so.
 */
export function warnMissingCommit(
  component: string,
  channel: CommitChannel | null
): void {
  if (channel || !import.meta.env?.DEV) return;
  console.error(
    `[${component}] no CommitKey provider: field commits will not fire. ` +
      `Provide the page's channel, or NO_COMMIT if this form has no events.`
  );
}
