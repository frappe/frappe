// `page.dialog` — the one dialog surface scripts are taught. `confirm` and
// `danger` are frappe-ui's own imperative dialogs, narrowed; `open` and `form`
// render on this page's own stack, which `<PageDialogs>` mounts.
//
// What the facade buys over importing frappe-ui's `dialog` directly:
//   - every verb is a promise, `null` meaning dismissed, so `if (!result) return`
//   - the page owns the stack, so navigating off the record cannot strand an
//     awaiting script behind a dialog the reader can no longer see
//   - opens are tagged with the running source, so a stuck dialog has a name
import { shallowRef, type Component, type Ref } from "vue";
import { dialog as frappeDialog } from "frappe-ui";
import { runningSource } from "./context";
import type {
  PageDialog,
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
   * Resolves the opener's promise. Idempotent, and deliberately separate from
   * `dismiss`: the promise settles the moment the answer is known, not when the
   * leave transition ends, so a page that unmounts mid-transition cannot turn a
   * submitted dialog into a cancelled one.
   */
  settle: (result?: any) => void;
  /** Takes the dialog off the stack — the host calls it after the leave transition. */
  dismiss: () => void;
  /** Set by the host component so navigating away still runs the author's `onCancel`. */
  onDismissed?: () => void;
}

export interface PageDialogHost {
  /**
   * True while a replay is running. A dialog opened from `refresh` re-opens on
   * every replay, so dev builds name the source rather than block the call —
   * a deliberate on-load gate stays possible.
   */
  isReplaying: () => boolean;
}

export interface PageDialogs {
  api: PageDialog;
  /** The renderable stack, oldest first. */
  entries: Ref<PageDialogEntry[]>;
  /**
   * The page is gone: close every open dialog newest-first, each promise
   * resolving `null`, and refuse every later open — with nothing left to render
   * them, a script awaiting one would wait forever.
   */
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
      };
      entries.value = [...entries.value, entry];
    });
  }

  // `confirm`/`danger` keep frappe-ui's own schema — it is the same object an
  // author would pass to `dialog.confirm` — and only gain the promise, the page
  // binding, and the replay warning.
  function native(
    verb: "confirm" | "danger",
    args: Record<string, any>,
  ): Promise<true | null> {
    if (detached) return refused(verb) as Promise<null>;
    warnOnReplay(verb);
    return new Promise((resolve) => {
      let handle: { close: () => void } | null = null;
      let settled = false;
      const settle = (result: true | null) => {
        if (settled) return;
        settled = true;
        untrack();
        resolve(result);
      };
      // Navigating away closes the dialog without frappe-ui firing `onCancel`,
      // so the promise is settled here rather than left to that callback.
      const untrack = track(() => {
        handle?.close();
        settle(null);
      });
      handle = frappeDialog[verb]({
        ...args,
        actions: args.actions?.map((action: Record<string, any>) => ({
          ...action,
          onClick: async (context: any) => {
            // An action with no `onClick` is frappe-ui's plain dismiss button;
            // answering `true` for it would read as a confirmation.
            if (!action.onClick) return settle(null);
            await action.onClick(context);
            settle(true);
          },
        })),
        onConfirm: async (context: any) => {
          await args.onConfirm?.(context);
          settle(true);
        },
        onCancel: () => {
          args.onCancel?.();
          settle(null);
        },
      });
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
