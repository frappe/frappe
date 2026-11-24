import { computed, onScopeDispose, ref, watch } from "vue";

const HISTORY_LIMIT = 50;
const COALESCE_MS = 400;

/**
 * Snapshot undo for one reactive document. Editors write into the document directly rather
 * than through a mutation layer, so a single deep watch is what covers all of them.
 */
export function useUndoHistory(state, apply, options = {}) {
  const {
    limit = HISTORY_LIMIT,
    coalesce = COALESCE_MS,
    ignore = [],
  } = options;
  const past = ref([]);
  const future = ref([]);
  let present = read();
  let timer = null;

  watch(state, schedule, { deep: true });
  onScopeDispose(clearTimer);

  /** Ignored keys stay out of the snapshot, so they neither record a step nor get restored. */
  function read() {
    const snapshot = { ...state };
    ignore.forEach((key) => delete snapshot[key]);
    return JSON.stringify(snapshot);
  }

  function clearTimer() {
    clearTimeout(timer);
    timer = null;
  }

  /** Typing lands one write per keystroke, and a burst of them is one step back. */
  function schedule() {
    clearTimer();
    timer = setTimeout(record, coalesce);
  }

  function record() {
    clearTimer();
    const next = read();
    if (next === present) return;
    past.value = [...past.value, present].slice(-limit);
    future.value = [];
    present = next;
  }

  /** Stepping leaves the document matching `present`, so the watch it wakes records nothing. */
  function step(from, to) {
    record();
    if (!from.value.length) return;
    to.value = [...to.value, present];
    present = from.value[from.value.length - 1];
    from.value = from.value.slice(0, -1);
    apply(JSON.parse(present));
  }

  /** Loading starts a new document: nothing before it is worth stepping back to. */
  function reset() {
    clearTimer();
    past.value = [];
    future.value = [];
    present = read();
  }

  /** A save writes its name and keys back, which is not an edit to step back over. */
  function absorb() {
    clearTimer();
    present = read();
  }

  return {
    canUndo: computed(() => past.value.length > 0),
    canRedo: computed(() => future.value.length > 0),
    undo: () => step(past, future),
    redo: () => step(future, past),
    flush: record,
    reset,
    absorb,
  };
}
