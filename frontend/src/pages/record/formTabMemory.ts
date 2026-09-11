// The form tab the reader last chose, per doctype, in this browser; keyed by user because
// a browser profile is shared and a choice is not.
const KEY = "frappe:desk:formTab";

type Stored = Record<string, Record<string, string>>;

export interface FormTabMemory {
  /** The identity the reader last chose for this doctype, or `""`. */
  recall(): string;
  remember(identity: string): void;
}

function read(): Stored {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function write(stored: Stored): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(stored));
  } catch {
    // Full or forbidden: the tab still switches for this page.
  }
}

export function formTabMemory(user: string, doctype: string): FormTabMemory {
  return {
    recall() {
      const identity = read()[user]?.[doctype];
      return typeof identity === "string" ? identity : "";
    },
    remember(identity) {
      const stored = read();
      write({ ...stored, [user]: { ...stored[user], [doctype]: identity } });
    },
  };
}
