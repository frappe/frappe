// Editor state for one doctype's Page Scripts: the list in run order, the
// script being edited, and its unsaved buffer. Saving publishes the doctype's
// realtime event, which is what makes a mounted Record page replay — the editor
// itself does nothing to the page.
import { computed, reactive, ref, toValue, watch } from "vue";
import type { MaybeRefOrGetter } from "vue";
import { errorMessage } from "../errorMessage";
import { pageScriptApi } from "./pageScriptApi";
import type { PageScriptDoc } from "./pageScriptApi";

export function usePageScriptEditor(
  doctype: MaybeRefOrGetter<string>,
  /**
   * The script a host addresses from outside — a URL, typically. Unknown and
   * absent names both fall back here rather than at the host, which has no
   * script list to check one against.
   */
  boundName?: MaybeRefOrGetter<string | undefined>,
) {
  const scripts = ref<PageScriptDoc[]>([]);
  const selectedName = ref<string | null>(toValue(boundName) ?? null);
  // One buffer per script, kept across selection changes and reloads: an edit
  // is only ever dropped by saving it or by deleting the script it belongs to.
  const buffers = reactive(new Map<string, string>());

  const loading = ref(false);
  const saving = ref(false);
  const error = ref("");

  // A reload that lands after a newer one must not overwrite it.
  let generation = 0;

  const selected = computed(
    () => scripts.value.find((row) => row.name === selectedName.value) ?? null,
  );

  const draft = computed<string>({
    get: () => bufferFor(selected.value),
    set: (value) => {
      if (selectedName.value) buffers.set(selectedName.value, value);
    },
  });

  const dirty = computed(() => isDirty(selected.value));

  // A doctype change is the one reload that *should* blank the pane: the list
  // on screen belongs to the doctype being left.
  watch(
    () => toValue(doctype),
    () => load(true),
    { immediate: true },
  );

  watch(
    () => toValue(boundName),
    (name) => {
      if (name === undefined || name === selectedName.value) return;
      // A name that arrives mid-load is taken on trust: the list it would be
      // checked against is the one still on its way, and `load` re-checks it.
      selectedName.value =
        loading.value || known(name) ? name : (lastName() ?? null);
    },
  );

  /**
   * `cold` means there is nothing on screen worth keeping, and it is the only
   * thing that raises `loading`.
   *
   * The distinction matters because `loading` drives a `v-if` over the whole
   * pane body: raising it for the reload that follows every write unmounted the
   * rail and the editor and rebuilt them, which threw away CodeMirror's undo
   * history, cursor, scroll and selection on each save. A reload that already
   * has a list keeps rendering it and swaps the rows when they land; `saving`
   * is what says a write is in flight.
   */
  async function load(cold = false) {
    const build = ++generation;
    loading.value = cold || scripts.value.length === 0;
    error.value = "";
    try {
      const rows = await pageScriptApi.list(toValue(doctype));
      if (build !== generation) return;
      scripts.value = rows;
      forgetVanished(rows);
      // Keep the author on the script they were editing; otherwise open the
      // last one, which is the one that runs last.
      if (!rows.some((row) => row.name === selectedName.value))
        selectedName.value = rows.at(-1)?.name ?? null;
    } catch (exception) {
      if (build !== generation) return;
      scripts.value = [];
      error.value = errorMessage(exception);
    } finally {
      if (build === generation) loading.value = false;
    }
  }

  function select(name: string | null) {
    selectedName.value = name;
  }

  function known(name: string) {
    return scripts.value.some((row) => row.name === name);
  }

  function lastName() {
    return scripts.value.at(-1)?.name ?? null;
  }

  /** Whether a row carries an unsaved edit — the list marks these. */
  function isDirty(row: PageScriptDoc | null) {
    return row !== null && bufferFor(row) !== row.script;
  }

  /**
   * Rethrows so the naming dialog can keep itself open and show why.
   *
   * `script` is the body the new script opens with — the empty state's starters
   * pass a working one for the verb they teach (ticket 37), so the author lands
   * in something that already runs. Omitted, the doctype's own default is what
   * prefills, which is what "start from an empty script" means.
   */
  async function create(name: string, script?: string) {
    await run(async () => {
      const created = await pageScriptApi.create({
        name,
        dt: toValue(doctype),
        run_order: nextRunOrder(),
        ...(script === undefined ? {} : { script }),
      });
      selectedName.value = created.name;
    });
  }

  async function save() {
    const row = selected.value;
    if (!row || !dirty.value) return;
    const text = draft.value;
    await mutate(async () => {
      const saved = await pageScriptApi.save({ ...row, script: text });
      // The saved document goes into the list *before* the buffer is dropped.
      // Otherwise `draft` falls back to this row's stale pre-save text for the
      // length of the reload — a visible revert-and-jump now that the reload no
      // longer blanks the pane. It also carries the fresh `modified` forward, so
      // a second save in that window is not refused by its own first one.
      absorb(saved);
      buffers.delete(row.name);
    });
  }

  /**
   * Folds a just-written document into the list the pane is still rendering.
   *
   * Tolerates a response without one rather than throwing: this runs inside the
   * save path, so a server that answers something unexpected would otherwise
   * take the whole save down — the buffer would never clear and the edit would
   * read as unsaved after a write that succeeded. The reload behind it is what
   * makes the list right in the end; this only spares the gap.
   */
  function absorb(doc: PageScriptDoc | undefined) {
    if (!doc?.name) return;
    const at = scripts.value.findIndex((row) => row.name === doc.name);
    if (at !== -1) scripts.value[at] = { ...scripts.value[at], ...doc };
  }

  /**
   * A disabled copy of `row`, carrying the buffer rather than the saved text —
   * duplicating a script you have been editing copies what you are looking at.
   * Disabled because an enabled copy would immediately run beside its original,
   * doubling whatever it does to the live page.
   */
  async function duplicate(row: PageScriptDoc) {
    const text = bufferFor(row);
    await mutate(async () => {
      const created = await pageScriptApi.create({
        name: copyName(row.name),
        dt: row.dt,
        view: row.view,
        script: text,
        enabled: 0,
        run_order: nextRunOrder(),
      });
      selectedName.value = created.name;
    });
  }

  /**
   * Where a new script goes: last, which is what keeps "the newest script wins by
   * default" true once anyone has dragged. Without it a new script takes the
   * doctype's default of 0 and would sort ahead of every positioned script.
   */
  function nextRunOrder() {
    return Math.max(0, ...scripts.value.map((row) => row.run_order ?? 0)) + 1;
  }

  /** `<name>-copy`, then `-copy-2`, … — the first one nothing else has taken. */
  function copyName(name: string) {
    const taken = new Set(scripts.value.map((row) => row.name));
    const base = `${name}-copy`;
    if (!taken.has(base)) return base;
    let suffix = 2;
    while (taken.has(`${base}-${suffix}`)) suffix += 1;
    return `${base}-${suffix}`;
  }

  /**
   * Moves the list to `names` and writes that order through immediately.
   *
   * Order is a property of the list, not of a script, so it joins neither the
   * per-script buffer nor Save: there is no such thing as an unsaved order.
   * The move lands locally first because the drop has already happened on
   * screen; a refusal is what puts the rail back, by re-reading the server's
   * order rather than by remembering the old one — the server's is the order
   * that is still true.
   */
  async function reorder(names: string[]) {
    const moved = names
      .map((name) => scripts.value.find((row) => row.name === name))
      .filter((row): row is PageScriptDoc => row !== undefined);
    // A list that lost or gained a row between the drag and the drop is not
    // one this reorder describes; the next load is what corrects it.
    if (moved.length !== scripts.value.length) return;

    scripts.value = moved;
    error.value = "";
    try {
      await pageScriptApi.reorder(toValue(doctype), names);
    } catch (exception) {
      // `load` clears `error` on its way in, so the failure is reported after
      // the revert, not before it.
      await load();
      error.value = errorMessage(exception);
    }
  }

  async function setEnabled(row: PageScriptDoc, enabled: boolean) {
    await mutate(() =>
      pageScriptApi.save({ ...row, enabled: enabled ? 1 : 0 }),
    );
  }

  async function remove(row: PageScriptDoc) {
    await mutate(async () => {
      await pageScriptApi.remove(row.name);
      buffers.delete(row.name);
    });
  }

  /** A write plus the reload that re-reads the server's order. Rethrows. */
  async function run(work: () => Promise<unknown>) {
    saving.value = true;
    error.value = "";
    try {
      await work();
      await load();
    } catch (exception) {
      error.value = errorMessage(exception);
      throw exception;
    } finally {
      saving.value = false;
    }
  }

  // Template handlers get the swallowing form: the failure is already on
  // `error`, and an unhandled rejection out of a DOM listener helps no one.
  async function mutate(work: () => Promise<unknown>) {
    try {
      await run(work);
    } catch {
      // shown through `error`
    }
  }

  function bufferFor(row: PageScriptDoc | null) {
    if (!row) return "";
    return buffers.get(row.name) ?? row.script;
  }

  function forgetVanished(rows: PageScriptDoc[]) {
    const names = new Set(rows.map((row) => row.name));
    for (const name of [...buffers.keys()])
      if (!names.has(name)) buffers.delete(name);
  }

  return {
    scripts,
    selected,
    selectedName,
    draft,
    dirty,
    isDirty,
    loading,
    saving,
    error,
    load,
    select,
    create,
    duplicate,
    save,
    setEnabled,
    reorder,
    remove,
  };
}

export type PageScriptEditorState = ReturnType<typeof usePageScriptEditor>;
