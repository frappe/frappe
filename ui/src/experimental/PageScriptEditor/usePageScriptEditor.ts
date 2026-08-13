// Editor state for one doctype's Page Scripts: the list in run order, the
// script being edited, and its unsaved buffer. Saving publishes the doctype's
// realtime event, which is what makes a mounted Record page replay — the editor
// itself does nothing to the page.
import { computed, reactive, ref, toValue, watch } from "vue";
import type { MaybeRefOrGetter } from "vue";
import { errorMessage } from "../errorMessage";
import { pageScriptApi } from "./pageScriptApi";
import type { PageScriptDoc } from "./pageScriptApi";

export function usePageScriptEditor(doctype: MaybeRefOrGetter<string>) {
  const scripts = ref<PageScriptDoc[]>([]);
  const selectedName = ref<string | null>(null);
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

  watch(() => toValue(doctype), load, { immediate: true });

  async function load() {
    const build = ++generation;
    loading.value = true;
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

  /** Whether a row carries an unsaved edit — the list marks these. */
  function isDirty(row: PageScriptDoc | null) {
    return row !== null && bufferFor(row) !== row.script;
  }

  // Rethrows so the naming dialog can keep itself open and show why.
  async function create(name: string) {
    await run(async () => {
      const created = await pageScriptApi.create({
        name,
        dt: toValue(doctype),
        run_order: nextRunOrder(),
      });
      selectedName.value = created.name;
    });
  }

  async function save() {
    const row = selected.value;
    if (!row || !dirty.value) return;
    const text = draft.value;
    await mutate(async () => {
      await pageScriptApi.save({ ...row, script: text });
      buffers.delete(row.name);
    });
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
    remove,
  };
}

export type PageScriptEditorState = ReturnType<typeof usePageScriptEditor>;
