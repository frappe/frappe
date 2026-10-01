// The form tab the reader last chose, per doctype, in this browser.
import { browserMemory } from "@/browserMemory";

export interface FormTabMemory {
  /** The identity the reader last chose for this doctype, or `""`. */
  recall(): string;
  remember(identity: string): void;
}

export function formTabMemory(user: string, doctype: string): FormTabMemory {
  const memory = browserMemory<Record<string, string>>("formTab", user);
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
