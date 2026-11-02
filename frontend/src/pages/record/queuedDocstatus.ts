// A Submit or Cancel that went through the Submission Queue: waits for its job, then fires `after*` or reports the failure.
import { __ } from "@/i18n";
import type { RealtimeSocket } from "@framework/ui/socket";
import {
  isQueued,
  queuedMessage,
  sendDocstatus,
  type DocstatusAct,
  type DocstatusChoice,
} from "./docstatusActs";
import { stripTags } from "./saveResponse";

/** What the failed job's `submission_failed` event carries. */
export interface QueueFailure {
  name: string;
  ref_doctype: string;
  ref_docname: string;
  exception?: string | null;
}

export interface DocstatusHost {
  socket: RealtimeSocket | undefined;
  /** The DocType queues its Submit and Cancel in the background. */
  queueing: () => boolean;
  isDirty: () => boolean;
  /** Reads the record again, keeping this wait alive, and returns it as the page now holds it. */
  load: () => Promise<Record<string, any>>;
  take: (document: Record<string, any>) => Promise<void>;
  fire: (event: string) => Promise<void>;
  info: (message: string) => void;
  failed: (act: DocstatusAct, failure: QueueFailure) => void;
  error: (error: unknown) => void;
}

/** The toast for a failed job: the act and the job's last error line. */
export function queueFailureMessage(
  act: DocstatusAct,
  failure: QueueFailure,
): string {
  const reason = stripTags(failure.exception ?? "");
  return act === "submit"
    ? __("Submit failed: {0}", [reason])
    : __("Cancel failed: {0}", [reason]);
}

export class DocstatusMover {
  private stopWatching = () => {};
  // Counts stops, so a reload that ends after one knows the reader has left.
  private stops = 0;

  constructor(private host: DocstatusHost) {}

  /** Resolves `{ queued: true }` when a job will act; the engine then skips `after*`, which `watch` fires. */
  async move(
    act: DocstatusAct,
    doctype: string,
    name: string,
    choice?: DocstatusChoice,
    modified?: string,
  ) {
    // Cancel all queues the root itself, so it never goes through the Submission Queue.
    const queue = this.host.queueing() && !choice?.all;
    // Listen before the request: a fast job can publish before the answer arrives.
    const wait = { settled: false };
    if (queue) {
      this.stop();
      this.watch(act, doctype, name, wait);
    }
    const stops = this.stops;
    let document: Record<string, any> | null;
    try {
      document = await sendDocstatus(doctype, name, act, queue, choice, modified);
    } catch (error) {
      this.stop();
      throw error;
    }
    if (document === null) {
      this.host.info(
        __(
          "The linked records are being cancelled in the background. You will be told when it finishes.",
        ),
      );
      return { queued: true as const };
    }
    // The job ended before the answer came: its event already fired `after*` or reported the failure.
    if (wait.settled) return { queued: true as const };
    if (stops !== this.stops) return;
    if (!isQueued(document, act)) {
      this.stop();
      await this.host.take(document);
      return;
    }
    this.host.info(queuedMessage(act));
    return { queued: true as const };
  }

  stop() {
    this.stops++;
    this.stopWatching();
    this.stopWatching = () => {};
  }

  // An unsaved edit is kept, and a reload that finds the record unmoved (another save) keeps waiting.
  private watch(
    act: DocstatusAct,
    doctype: string,
    name: string,
    wait: { settled: boolean },
  ) {
    const socket = this.host.socket;
    if (!socket) return;
    const settle = () => {
      wait.settled = true;
      this.stop();
    };
    const onUpdated = async (...args: unknown[]) => {
      const event = args[0] as { doctype?: string; name?: string } | undefined;
      if (
        event?.doctype !== doctype ||
        event.name !== name ||
        this.host.isDirty()
      )
        return;
      const stops = this.stops;
      let document: Record<string, any>;
      try {
        document = await this.host.load();
      } catch (error) {
        return this.host.error(error);
      }
      if (stops !== this.stops || wait.settled || isQueued(document, act))
        return;
      settle();
      await this.host
        .fire(act === "submit" ? "afterSubmit" : "afterCancel")
        .catch(this.host.error);
    };
    const onFailed = (...args: unknown[]) => {
      const failure = args[0] as QueueFailure | undefined;
      if (
        failure?.ref_doctype !== doctype ||
        failure.ref_docname !== name ||
        wait.settled
      )
        return;
      settle();
      this.host.failed(act, failure);
    };
    socket.on("doc_update", onUpdated);
    socket.on("submission_failed", onFailed);
    this.stopWatching = () => {
      socket.off("doc_update", onUpdated);
      socket.off("submission_failed", onFailed);
    };
  }
}
