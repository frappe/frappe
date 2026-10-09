import { call } from "frappe-ui";
import {
  computed,
  onUnmounted,
  ref,
  toValue,
  watch,
  type MaybeRefOrGetter,
  type Ref,
} from "vue";
import { getSocketInstance, subscribeToDoc } from "../../socket";
import { cint } from "./dataImport";
import { t } from "./translate";
import type {
  DataImportDoc,
  DataImportLog,
  DataImportLogFilter,
  DataImportPreview,
  DataImportProgress,
  DataImportStatusSummary,
  DocType,
  ImportProviderSchema,
} from "./types";

const DOCTYPE = "Data Import";
const METHODS = "frappe.core.doctype.data_import.data_import";
const PROGRESS_COUNTS_MIN_INTERVAL_MS = 2000;
const RECENT_ACTIVITY_LIMIT = 5;

interface ProgressEvent {
  data_import: string;
  current: number;
  total: number;
  eta?: number;
  inserted?: number;
  updated?: number;
  failed?: number;
  skipping?: boolean;
  row_indexes?: number[];
  activity?: { kind?: string; text?: string; is_html?: boolean };
}

export interface StopImportResponse {
  status: "success" | "not_running";
  message: string;
}

export function useDataImport(
  name: Ref<string | null>,
  // A getter lets a page that stays mounted start the next new import on another doctype.
  options: { doctype?: MaybeRefOrGetter<string | undefined> } = {}
) {
  const socket = getSocketInstance();

  const doc = ref<DataImportDoc>(newDoc(toValue(options.doctype)));
  // the doc as the server last sent it, to tell local edits apart
  const savedDoc = ref<string | null>(null);
  const loading = ref(false);
  const saving = ref(false);

  const preview = ref<DataImportPreview | null>(null);
  const previewSource = ref<string | null>(null);
  const previewLoading = ref(false);
  const previewError = ref<string | null>(null);

  // Set from the moment Start is pressed or progress arrives, since the worker only
  // writes "In Progress" once it picks the job up.
  const startedHere = ref(false);
  const progress = ref<DataImportProgress | null>(null);
  const importStatus = ref<DataImportStatusSummary | null>(null);
  const blocked = ref(false);

  const logFilter = ref<DataImportLogFilter>("all");
  const logs = ref<DataImportLog[]>([]);

  const providerSchema = ref<ImportProviderSchema | null>(null);
  const doctypeMeta = ref<DocType[] | null>(null);

  const isNew = computed(() => !doc.value.name);
  const dirty = computed(
    () => isNew.value || JSON.stringify(doc.value) !== savedDoc.value
  );
  const hasImportFile = computed(
    () => !!(doc.value.import_file || doc.value.google_sheets_url)
  );
  const running = computed(
    () =>
      doc.value.status === "In Progress" ||
      (startedHere.value && doc.value.status === "Pending")
  );
  const importStarted = computed(
    () => running.value || doc.value.status !== "Pending"
  );
  // what the preview was built from; a change means it no longer applies
  const sourceKey = computed(() =>
    [
      doc.value.import_file || "",
      doc.value.google_sheets_url || "",
      doc.value.use_csv_sniffer ? 1 : 0,
      doc.value.custom_delimiters ? 1 : 0,
      doc.value.delimiter_options || "",
    ].join("|")
  );
  const previewReady = computed(
    () => !!preview.value && previewSource.value === sourceKey.value
  );

  // Bumped whenever another import is opened, so late answers for the old one are dropped.
  let generation = 0;
  const track = () => {
    const at = generation;
    return () => at === generation;
  };

  let previewRequest = 0;
  let previewPromise: Promise<DataImportPreview | null> | null = null;
  // a file that failed to load is not fetched again until asked to
  let previewFailedSource: string | null = null;
  let logsRequest = 0;
  let countsFetchedAt = 0;
  let countsInFlight = false;
  let leaveRoom: (() => void) | undefined;

  function applyServerDoc(serverDoc: DataImportDoc) {
    savedDoc.value = JSON.stringify(serverDoc);
    doc.value = serverDoc;
    if (serverDoc.status !== "Pending") return;
    // Missing records that can be made from the file's value default to being
    // created; it is an unsaved edit, so Save sends it.
    for (const mapping of doc.value.value_mappings) {
      if (mapping.can_create && !mapping.target_value && !mapping.create_new)
        mapping.create_new = 1;
    }
  }

  function open(next: string | null) {
    generation += 1;
    previewRequest += 1;
    previewPromise = null;
    previewFailedSource = null;
    countsFetchedAt = 0;
    countsInFlight = false;
    doc.value = newDoc(toValue(options.doctype));
    savedDoc.value = null;
    preview.value = null;
    previewSource.value = null;
    previewLoading.value = false;
    previewError.value = null;
    startedHere.value = false;
    progress.value = null;
    importStatus.value = null;
    blocked.value = false;
    logFilter.value = "all";
    logs.value = [];
    joinRoom(next);
    if (next) reload().catch(() => {});
  }

  function joinRoom(docname: string | null) {
    leaveRoom?.();
    leaveRoom = docname ? subscribeToDoc(socket, DOCTYPE, docname) : undefined;
  }

  async function reload() {
    const docname = name.value;
    if (!docname) return;
    const isCurrent = track();
    loading.value = true;
    try {
      const serverDoc = await call<DataImportDoc>("frappe.client.get", {
        doctype: DOCTYPE,
        name: docname,
      });
      if (!isCurrent()) return;
      applyServerDoc(serverDoc);
      afterLoad();
    } finally {
      if (isCurrent()) loading.value = false;
    }
  }

  // Desk's form `refresh`: what to fetch depends on where the import stands.
  function afterLoad() {
    startedHere.value = running.value;
    if (running.value) {
      progress.value ??= emptyProgress();
      refreshProgressCounts();
    } else {
      progress.value = null;
    }
    if (
      hasImportFile.value &&
      !previewReady.value &&
      previewFailedSource !== sourceKey.value
    ) {
      fetchPreview();
    }
    if (doc.value.status !== "Pending" && !running.value)
      loadLogs().catch(() => {});
  }

  /** Inserts a new import, saves an existing one, then fetches the preview again. */
  async function save(): Promise<DataImportDoc> {
    const wasNew = isNew.value;
    const isCurrent = track();
    saving.value = true;
    try {
      const serverDoc = await call<DataImportDoc>(
        wasNew ? "frappe.client.insert" : "frappe.client.save",
        { doc: doc.value }
      );
      if (!isCurrent()) return serverDoc;
      // The server rebuilds value_mappings and may clear template_warnings, so take its copy.
      applyServerDoc(serverDoc);
      if (wasNew) name.value = serverDoc.name!;
      if (hasImportFile.value && !importStarted.value)
        fetchPreview({ force: true });
      return serverDoc;
    } finally {
      if (isCurrent()) saving.value = false;
    }
  }

  /**
   * Parallel calls share one request; `force` drops the one in flight and clears a
   * remembered failure. Resolves to null when the preview failed or no longer applies.
   */
  function fetchPreview({ force = false } = {}) {
    if (!hasImportFile.value) {
      previewRequest += 1;
      previewPromise = null;
      preview.value = null;
      previewSource.value = null;
      previewError.value = null;
      previewLoading.value = false;
      return Promise.resolve(null);
    }
    if (isNew.value) return Promise.resolve(null);
    const source = sourceKey.value;
    if (!force && previewFailedSource === source) return Promise.resolve(null);
    if (previewPromise && !force) return previewPromise;

    const request = ++previewRequest;
    const docname = doc.value.name;
    const isStale = () =>
      request !== previewRequest ||
      doc.value.name !== docname ||
      sourceKey.value !== source;

    previewFailedSource = null;
    previewError.value = null;
    previewLoading.value = true;
    previewPromise = call<DataImportPreview | null>(
      `${METHODS}.get_preview_from_template`,
      {
        data_import: docname,
        import_file: doc.value.import_file,
        google_sheets_url: doc.value.google_sheets_url,
      }
    )
      .then((data) => {
        if (isStale()) return null;
        if (!data) throw new Error(t("Failed to load import file"));
        preview.value = data;
        previewSource.value = source;
        return data;
      })
      .catch((error) => {
        if (isStale()) return null;
        preview.value = null;
        previewSource.value = null;
        previewFailedSource = source;
        previewError.value = previewErrorMessage(error);
        return null;
      })
      .finally(() => {
        if (request !== previewRequest) return;
        previewPromise = null;
        previewLoading.value = false;
      });
    return previewPromise;
  }

  /**
   * The sheet can change without its URL changing, so the warnings saved by a
   * blocked run no longer apply. Only offered while there are no unsaved edits,
   * so the cleared warnings stay out of `dirty`.
   */
  function refreshGoogleSheet() {
    if (doc.value.template_warnings) {
      doc.value.template_warnings = "";
      savedDoc.value = JSON.stringify(doc.value);
    }
    return fetchPreview({ force: true });
  }

  /** Resolves true when the job was queued, false when it was already queued or failed. */
  async function start(): Promise<boolean> {
    const docname = name.value;
    if (!docname) return false;
    blocked.value = false;
    startedHere.value = true;
    progress.value = emptyProgress();
    try {
      const started = await call<boolean>(`${METHODS}.form_start_import`, {
        data_import: docname,
      });
      return started === true;
    } catch {
      if (name.value === docname) {
        startedHere.value = false;
        progress.value = null;
      }
      return false;
    }
  }

  async function stop(): Promise<StopImportResponse | undefined> {
    const docname = name.value;
    if (!docname) return;
    const response = await call<StopImportResponse>(
      `${METHODS}.stop_data_import`,
      { doc_name: docname }
    );
    await reload();
    return response;
  }

  // Counts for a run that was already going when the import was opened.
  async function refreshProgressCounts() {
    const docname = name.value;
    if (!docname || !running.value || countsInFlight) return;
    if (Date.now() - countsFetchedAt < PROGRESS_COUNTS_MIN_INTERVAL_MS) return;
    const isCurrent = track();
    countsFetchedAt = Date.now();
    countsInFlight = true;
    try {
      const status = await call<DataImportStatusSummary>(
        `${METHODS}.get_import_status`,
        { data_import_name: docname }
      );
      if (!isCurrent()) return;
      importStatus.value = status;
      const previous = progress.value ?? emptyProgress();
      const upsert = doc.value.import_type === "Insert or Update Records";
      progress.value = {
        ...previous,
        current: Number(status.processed_records || previous.current),
        total: Number(status.total_records || previous.total),
        inserted: Number(
          (upsert ? status.inserted : status.inserted ?? status.success) ?? 0
        ),
        updated: Number(status.updated ?? 0),
        failed: Number(status.failed ?? 0),
      };
    } catch {
      // the next progress event carries the counts too
    } finally {
      if (isCurrent()) countsInFlight = false;
    }
  }

  /** The status summary first (the log tabs count from it), then the rows for the filter. */
  async function loadLogs() {
    const docname = name.value;
    if (!docname) return;
    const isCurrent = track();
    const request = ++logsRequest;
    const status = await call<DataImportStatusSummary>(
      `${METHODS}.get_import_status`,
      { data_import_name: docname }
    ).catch(() => importStatus.value);
    if (!isCurrent() || request !== logsRequest) return;
    importStatus.value = status;
    const rows = await call<DataImportLog[]>(`${METHODS}.get_import_logs`, {
      data_import: docname,
      status: logFilter.value,
    });
    if (!isCurrent() || request !== logsRequest) return;
    logs.value = rows ?? [];
  }

  async function loadImportFields(doctype: string | undefined) {
    providerSchema.value = null;
    doctypeMeta.value = null;
    if (!doctype) return;
    const isCurrent = () => doc.value.reference_doctype === doctype;
    const schema = await call<ImportProviderSchema | null>(
      `${METHODS}.get_import_fields`,
      { doctype }
    ).catch(() => null);
    if (!isCurrent()) return;
    providerSchema.value = schema ?? null;
    const meta = await call<{ docs: DocType[] }>(
      "frappe.desk.form.load.getdoctype",
      { doctype, with_parent: 1 }
    );
    if (isCurrent()) doctypeMeta.value = meta.docs;
  }

  const forThisImport = (payload: unknown) =>
    !!name.value &&
    (payload as { data_import?: string } | null)?.data_import === name.value;

  function onRefresh(payload: unknown) {
    if (!forThisImport(payload)) return;
    startedHere.value = false;
    progress.value = null;
    reload().catch(() => {});
  }

  function onBlocked(payload: unknown) {
    if (!forThisImport(payload)) return;
    startedHere.value = false;
    progress.value = null;
    const isCurrent = track();
    // the blocked run saved its warnings, so they are only on the server's copy
    reload()
      .then(() => {
        if (isCurrent()) blocked.value = true;
      })
      .catch(() => {});
  }

  function onProgress(payload: unknown) {
    if (!forThisImport(payload)) return;
    startedHere.value = true;
    progress.value = nextProgress(progress.value, payload as ProgressEvent);
  }

  const handlers: Record<string, (payload: unknown) => void> = {
    data_import_refresh: onRefresh,
    data_import_blocked: onBlocked,
    data_import_progress: onProgress,
  };
  if (socket) for (const event in handlers) socket.on(event, handlers[event]);

  watch(
    name,
    (next) => {
      // the first save names the import already open here; that is not another import
      if (next && next === doc.value.name) joinRoom(next);
      else open(next);
    },
    { immediate: true }
  );
  watch(
    () => doc.value.reference_doctype,
    (doctype) => loadImportFields(doctype).catch(() => {}),
    { immediate: true }
  );
  watch(logFilter, () => {
    if (importStarted.value && !running.value) loadLogs().catch(() => {});
  });

  onUnmounted(() => {
    generation += 1;
    leaveRoom?.();
    leaveRoom = undefined;
    if (socket)
      for (const event in handlers) socket.off(event, handlers[event]);
  });

  return {
    doc,
    isNew,
    dirty,
    loading,
    saving,
    hasImportFile,
    reload,
    save,

    preview,
    previewReady,
    previewLoading,
    previewError,
    fetchPreview,
    refreshGoogleSheet,

    running,
    importStarted,
    progress,
    importStatus,
    blocked,
    start,
    stop,

    logFilter,
    logs,
    loadLogs,

    providerSchema,
    doctypeMeta,
  };
}

export type UseDataImport = ReturnType<typeof useDataImport>;

function newDoc(doctype: string | undefined): DataImportDoc {
  return {
    doctype: DOCTYPE,
    reference_doctype: doctype ?? "",
    import_type: "Insert New Records",
    status: "Pending",
    import_file: null,
    google_sheets_url: null,
    mute_emails: 1,
    submit_after_import: 0,
    use_csv_sniffer: 0,
    custom_delimiters: 0,
    delimiter_options: ",;\\\\t|",
    value_mappings: [],
    skipped_rows: [],
  };
}

export function emptyProgress(): DataImportProgress {
  return {
    current: 0,
    total: 0,
    eta: 0,
    inserted: 0,
    updated: 0,
    failed: 0,
    skipping: false,
    recentActivity: [],
  };
}

/** Counts missing from an event keep their last value; a repeat of the newest activity is dropped. */
function nextProgress(
  previous: DataImportProgress | null,
  event: ProgressEvent
): DataImportProgress {
  const prev = previous ?? emptyProgress();
  let recentActivity = prev.recentActivity;
  if (event.activity?.text) {
    const incoming = {
      kind: event.activity.kind || "info",
      text: event.activity.text,
      isHtml: !!event.activity.is_html,
      row: cint(event.row_indexes?.[0]) || null,
    };
    const latest = recentActivity[0];
    const repeatsLatest =
      latest &&
      latest.kind === incoming.kind &&
      latest.text === incoming.text &&
      latest.isHtml === incoming.isHtml;
    if (!repeatsLatest)
      recentActivity = [incoming, ...recentActivity].slice(
        0,
        RECENT_ACTIVITY_LIMIT
      );
  }
  return {
    current: cint(event.current),
    total: cint(event.total),
    eta: Math.max(cint(event.eta), 0),
    inserted: cint(event.inserted, prev.inserted),
    updated: cint(event.updated, prev.updated),
    failed: cint(event.failed, prev.failed),
    skipping: !!event.skipping,
    recentActivity,
  };
}

function previewErrorMessage(error: unknown): string {
  const { messages, message } = (error ?? {}) as {
    messages?: string[];
    message?: string;
  };
  if (messages?.length) return messages.join(" ");
  if (typeof message === "string" && message) return message;
  return t("Failed to load import file");
}
