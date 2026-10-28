// `page.dialog`: `confirm` and `danger` are frappe-ui's own dialogs, narrowed as `shell.dialog` narrows them;
// `open` and `form` render on this page's own stack, which `<PageDialogs>` mounts.
import { shallowRef, type Component, type Ref } from "vue";
import { openNarrowedDialog } from "@/narrowedDialog";
import { runningSource } from "./context";
import type {
  PageDialog,
  PageDialogConfirmOptions,
  PageDialogFormOptions,
  PageDialogOpenOptions,
} from "./types";

/** One dialog this page is rendering. */
export interface PageDialogEntry {
  id: number;
  /** The script that opened it — who a failure or a stuck dialog is named after. */
  source: string;
  kind: "component" | "form";
  /** `open`: what renders inside the host dialog, and its chrome. */
  component?: Component;
  props: Record<string, any>;
  options: PageDialogOpenOptions;
  /** `form`: what the form host renders. */
  form?: PageDialogFormOptions;
  /**
   * Resolves the opener's promise. Separate from `dismiss` so a page unmounting
   * mid-transition cannot turn a submitted dialog into a cancelled one.
   */
  settle: (result?: any) => void;
  /** Takes the dialog off the stack — the host calls it after the leave transition. */
  dismiss: () => void;
  /** Runs one of the author's callbacks so its ops paint once, when it finishes. */
  hold: PageDialogHost["hold"];
  /** Set by the host component so navigating away still runs the author's `onCancel`. */
  onDismissed?: () => void;
}

export interface PageDialogHost {
  /** True while a replay is running; a dialog opened from `refresh` re-opens on every replay. */
  isReplaying: () => boolean;
  /** Runs a dialog's script callback so its ops paint once, when it finishes. */
  hold: <T>(work: () => Promise<T> | T) => Promise<T>;
}

export interface PageDialogs {
  api: PageDialog;
  /** The renderable stack, oldest first. */
  entries: Ref<PageDialogEntry[]>;
  /** Closes every open dialog newest-first, each resolving `null`, and refuses every later open. */
  closeAll: () => void;
}

let nextId = 0;

export function createPageDialogs(host: PageDialogHost): PageDialogs {
  const entries = shallowRef<PageDialogEntry[]>([]);
  // Every open dialog's dismisser, in open order — including the `confirm` and
  // `danger` ones frappe-ui renders, which never reach `entries`.
  const openDialogs: Array<() => void> = [];
  let detached = false;

  function track(dismiss: () => void) {
    openDialogs.push(dismiss);
    return () => {
      const index = openDialogs.indexOf(dismiss);
      if (index >= 0) openDialogs.splice(index, 1);
    };
  }

  function warn(verb: string, reason: string) {
    if (!import.meta.env.DEV) return;
    console.warn(
      `[record-page] ${runningSource()} called page.dialog.${verb} ${reason}`,
    );
  }

  /** Nothing renders a dialog opened after the page went away. */
  function refused(verb: string) {
    warn(verb, "after leaving the record — it resolves null unopened");
    return Promise.resolve(null);
  }

  function warnOnReplay(verb: string) {
    if (!host.isReplaying()) return;
    warn(
      verb,
      "during a replay — it will re-open on every refresh. Dialogs belong in `run` and event handlers, not `refresh`.",
    );
  }

  function mount(
    verb: "open" | "form",
    build: () => {
      kind: PageDialogEntry["kind"];
      component?: Component;
      props?: Record<string, any>;
      options?: PageDialogOpenOptions;
      form?: PageDialogFormOptions;
    },
  ): Promise<any> {
    if (detached) return refused(verb);
    warnOnReplay(verb);
    const source = runningSource();
    return new Promise((resolve) => {
      const id = nextId++;
      let settled = false;
      const settle = (result: any = null) => {
        if (settled) return;
        settled = true;
        untrack();
        resolve(result ?? null);
      };
      const dismiss = () => {
        entries.value = entries.value.filter((entry) => entry.id !== id);
      };
      const untrack = track(() => {
        entry.onDismissed?.();
        settle(null);
        dismiss();
      });
      const entry: PageDialogEntry = {
        id,
        source,
        props: {},
        options: {},
        ...build(),
        settle,
        dismiss,
        hold: host.hold,
      };
      entries.value = [...entries.value, entry];
    });
  }

  function native(
    verb: "confirm" | "danger",
    args: PageDialogConfirmOptions,
  ): Promise<true | null> {
    if (detached) return refused(verb) as Promise<null>;
    warnOnReplay(verb);
    const source = runningSource();
    return openNarrowedDialog(verb, args, {
      hold: host.hold,
      warn: (reason) => warn(verb, reason),
      failed: (exception) =>
        console.error(
          `[record-page] ${source} page.dialog.${verb} onCancel threw`,
          exception,
        ),
      track,
    });
  }

  const api: PageDialog = {
    open: (component, props = {}, options = {}) =>
      mount("open", () => ({ kind: "component", component, props, options })),
    form: (options) => mount("form", () => ({ kind: "form", form: options })),
    confirm: (args) => native("confirm", args ?? {}),
    danger: (args) => native("danger", args ?? {}),
  };

  return {
    api,
    entries,
    closeAll: () => {
      detached = true;
      for (const dismiss of [...openDialogs].reverse()) dismiss();
    },
  };
}
