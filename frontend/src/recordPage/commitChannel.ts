// Turns a field's commit into the event key a script's handler is registered under,
// so events are dispatched where the value changed, not diffed out of the document.
import type {
  CommitChannel,
  RowAddress,
  RowChange,
} from "@framework/ui/components/Fields/types";
import { ROW_EVENTS } from "./flattenHandlers";

export interface CommitChannelHost {
  dispatch: (event: string, row?: RowAddress) => Promise<void> | void;
}

export interface RecordCommitChannel extends CommitChannel {
  /** Fires the handler of an edit whose commit never arrived, and waits for the handlers already running. */
  flush: () => Promise<void>;
}

interface Edit {
  event: string;
  value: any;
  row?: RowAddress;
}

export function createCommitChannel(
  host: CommitChannelHost,
): RecordCommitChannel {
  let pending: Edit | null = null;
  let settled: Edit | null = null;
  // Handlers a commit started and nobody awaited; a save waits for them before `beforeSave`.
  const running = new Set<Promise<void>>();

  // An echo of the value already committed is a no-op: a control that re-emits as it
  // commits, or the `change` a save's repaint fires on a focused input, must not refire.
  function settles(event: string, value: any, row?: RowAddress): boolean {
    return !(
      settled?.event === event &&
      settled.row?.key === row?.key &&
      Object.is(settled.value, value)
    );
  }

  function track(dispatched: Promise<void> | void) {
    if (!dispatched) return;
    const done = dispatched.finally(() => running.delete(done));
    running.add(done);
    return done;
  }

  function commit(fieldname: string, value: any, row?: RowAddress) {
    const event = fieldEvent(fieldname, row);
    pending = null;
    if (!settles(event, value, row)) return;
    settled = { event, value, row };
    return track(host.dispatch(event, row));
  }

  return {
    pending: (fieldname, value, row) => {
      const event = fieldEvent(fieldname, row);
      if (settles(event, value, row)) pending = { event, value, row };
    },
    commit,
    rowChanged: (row, change) => {
      // A structural edit is itself a commit, and a removed row's pending edit has nowhere to land.
      pending = null;
      // A removed row has no address left to hand on; its handle would throw on every access.
      track(host.dispatch(rowEvent(row, change), change === "add" ? row : undefined));
    },
    flush: async () => {
      const edit = pending;
      if (edit) {
        pending = null;
        settled = edit;
        await host.dispatch(edit.event, edit.row);
      }
      await Promise.all([...running]);
    },
  };
}

/** A child field is addressed by its table, on the one character a fieldname cannot hold. */
export function fieldEvent(fieldname: string, row?: RowAddress): string {
  return row ? `${row.parentfield}.${fieldname}` : fieldname;
}

/** The lifecycle keys are `on`-prefixed, so they cannot collide with a child field called `add`. */
export function rowEvent(row: RowAddress, change: RowChange): string {
  return `${row.parentfield}.${ROW_EVENTS[change]}`;
}
