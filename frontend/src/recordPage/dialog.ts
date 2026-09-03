// `page.dialog`: `confirm` and `danger` are frappe-ui's own dialogs, narrowed;
// `open` and `form` render on this page's own stack, which `<PageDialogs>` mounts.
import { shallowRef, type Component, type Ref } from "vue";
import { dialog as frappeDialog } from "frappe-ui";
import { runningSource } from "./context";
import type {
  PageDialog,
  PageDialogConfirmAction,
  PageDialogConfirmOptions,
  PageDialogControl,
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
  /** Set by the host component so navigating away still runs the author's `onCancel`. */
  onDismissed?: () => void;
}

export interface PageDialogHost {
  /** True while a replay is running; a dialog opened from `refresh` re-opens on every replay. */
  isReplaying: () => boolean;
}

export interface PageDialogs {
  api: PageDialog;
  /** The renderable stack, oldest first. */
  entries: Ref<PageDialogEntry[]>;
  /** Closes every open dialog newest-first, each resolving `null`, and refuses every later open. */
  closeAll: () => void;
}

// frappe-ui's `ConfirmArgs`, named key by key: an option not named here is dropped.
const CONFIRM_OPTIONS = [
  "title",
  "message",
  "confirmLabel",
  "cancelLabel",
  "theme",
  "icon",
  "size",
  "dismissible",
  "onConfirm",
  "onCancel",
  "actions",
];

// frappe-ui forces red and its own icon on `danger`, so passing either is the mistake warned about.
const DANGER_OPTIONS = CONFIRM_OPTIONS.filter(
  (option) => option !== "theme" && option !== "icon",
);

// frappe-ui's `DialogAction` is a whole button's prop surface; these five are what `page` means by an action.
const ACTION_OPTIONS = ["label", "variant", "theme", "icon", "onClick"];

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

  /** Keeps the named keys and drops the rest, saying which it dropped. */
  function pick(
    verb: string,
    from: Record<string, any>,
    named: string[],
    where = "",
  ) {
    const kept: Record<string, any> = {};
    for (const [key, value] of Object.entries(from)) {
      if (named.includes(key)) kept[key] = value;
      else
        warn(
          verb,
          `with '${key}'${where}, which it does not forward — dropped. See COMPATIBILITY.md.`,
        );
    }
    return kept;
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

  // Curated three layers deep: the options, the nested actions, and the object each callback receives.
  function native(
    verb: "confirm" | "danger",
    args: PageDialogConfirmOptions,
  ): Promise<true | null> {
    if (detached) return refused(verb) as Promise<null>;
    warnOnReplay(verb);
    const options = pick(
      verb,
      args,
      verb === "danger" ? DANGER_OPTIONS : CONFIRM_OPTIONS,
    );
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
        ...options,
        actions: args.actions?.map((action: PageDialogConfirmAction) => ({
          ...pick(verb, action, ACTION_OPTIONS, ` on action '${action.label}'`),
          onClick: async (control: any) => {
            // An action with no `onClick` is frappe-ui's plain dismiss button;
            // answering `true` for it would read as a confirmation.
            if (!action.onClick) return settle(null);
            await action.onClick(controlFor(control));
            settle(true);
          },
        })),
        onConfirm: async (control: any) => {
          await args.onConfirm?.(controlFor(control));
          settle(true);
        },
        onCancel: () => {
          args.onCancel?.();
          settle(null);
        },
      } as any);
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

// The engine's own object, not frappe-ui's `DialogControl`: a rename underneath must not change a stored script.
function controlFor(control: any): PageDialogControl {
  return {
    close: () => control?.close?.(),
    setError: (message) => control?.setError?.(message),
  };
}
