// The form tab the reader last chose, per doctype, in this browser.
import { browserMemory } from "@/browserMemory";

export interface FormTabMemory {
  /** The identity the reader last chose for this doctype, or `""`. */
  recall(): string;
  remember(identity: string): void;
}

export function formTabMemory(user: string, doctype: string): FormTabMemory {
  const memory = browserMemory("formTab", user, isTabs);
  return {
    recall() {
      const identity = memory.recall()?.[doctype];
      return typeof identity === "string" ? identity : "";
    },
    remember(identity) {
      memory.remember({ ...memory.recall(), [doctype]: identity });
    },
  };
}

function isTabs(value: unknown): value is Record<string, string> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}
