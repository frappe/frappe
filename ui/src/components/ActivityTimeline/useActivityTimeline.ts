import { createResource } from "frappe-ui";
import { computed, onMounted, onUnmounted, reactive, ref, type Ref } from "vue";
import { getSocketInstance } from "../../socket";
import type {
  Activity,
  CustomActivity,
  LogActivity,
  Pagination,
  UserInfo,
  VersionActivity,
  VersionChange,
} from "./types";
import { getAssignee, stripHtml } from "./utils";

// One resource per doctype:docname for the session, so reopening a doc is instant.
const resources = new Map<string, ReturnType<typeof createResource>>();

// "older emails remain" flag, kept outside the resource so it survives cached remounts.
const hasMoreEmailsByKey = new Map<string, Ref<boolean>>();

export function useActivityTimeline(
  doctype: string,
  docname: string,
  paginate?: boolean
) {
  const cacheKey = `${doctype}:${docname}`;

  let hasMoreEmails = hasMoreEmailsByKey.get(cacheKey);
  if (!hasMoreEmails) {
    hasMoreEmails = ref(true);
    hasMoreEmailsByKey.set(cacheKey, hasMoreEmails);
  }

  let resource = resources.get(cacheKey);
  if (!resource) {
    resource = createResource({
      url: "frappe.desk.form.activity.get_activity_timeline",
      params: { doctype, name: docname },
      cache: `activities:${cacheKey}`,
      auto: true,
      // transform only sets resource.data; onSuccess still sees the raw response,
      // so has_more_emails is read there (not from transform's output).
      transform: (res: { activities: Activity[] }) => res.activities,
      onSuccess: (res: { has_more_emails?: boolean }) => {
        hasMoreEmails!.value = !!res.has_more_emails;
      },
    });
    resources.set(cacheKey, resource);
  }

  subscribeToLiveUpdates(doctype, docname, resource);

  const activities = computed<Array<Activity | CustomActivity>>(() => {
    const fetched = (resource.data as Activity[] | undefined) ?? [];
    const uniqueActivities = dropDuplicateKeys(fetched);
    uniqueActivities.sort(compareActivities);
    return groupActivities(uniqueActivities);
  });

  return {
    activities,
    loading: computed<boolean>(() => resource.loading),
    reload: () => resource.reload(),
    paginate: paginate
      ? createEmailPagination(doctype, docname, resource, hasMoreEmails)
      : undefined,
  };
}

// Email paging: fetch the next older page and append; the activities computed re-sorts.
function createEmailPagination(
  doctype: string,
  docname: string,
  resource: ReturnType<typeof createResource>,
  hasMoreEmails: Ref<boolean>
): Pagination {
  const olderEmails = createResource({
    url: "frappe.desk.form.activity.get_more_email_activities",
    auto: false,
    onSuccess: (res: { activities: Activity[]; has_more_emails?: boolean }) => {
      const loaded = (resource.data as Activity[] | undefined) ?? [];
      resource.data = [...loaded, ...res.activities];
      hasMoreEmails.value = !!res.has_more_emails;
    },
  });

  const fetchNextPage = () => {
    if (olderEmails.loading || !hasMoreEmails.value) return;
    const loaded = (resource.data as Activity[] | undefined) ?? [];
    // count-based offset: emails are only appended, so the loaded count is the next start
    const emailsLoaded = loaded.filter((a) => a.type === "email").length;
    olderEmails.submit({ doctype, name: docname, start: emailsLoaded });
  };

  // reactive() so the refs unwrap when read through the `paginate` prop.
  return reactive({
    hasNextPage: computed(() => hasMoreEmails.value),
    isFetchingNextPage: computed(() => olderEmails.loading),
    fetchNextPage,
    // in-feed row above the oldest email; email-specific copy lives here, not in the component
    loadMore: {
      position: "inline" as const,
      label: "Show previous conversations",
      icon: "lucide-chevrons-up",
    },
  });
}

function subscribeToLiveUpdates(
  doctype: string,
  docname: string,
  resource: ReturnType<typeof createResource>
) {
  const socket = getSocketInstance();
  if (!socket) return;

  // The socket payload has no avatar — reuse a resolved author from the feed, else fall back.
  const resolveAuthor = (email: string | undefined, fallback: UserInfo) => {
    if (!email) return fallback;
    const known = ((resource.data as Activity[] | undefined) ?? []).find(
      (a) => a.author?.email === email
    )?.author;
    return known ?? fallback;
  };

  const onUpdate = (payload: unknown) => {
    const { doc, key, action } = payload as {
      doc: Record<string, unknown>;
      key: string;
      action: "add" | "update" | "delete";
    };
    const activity = normalizeLiveActivity(key, doc, resolveAuthor);
    if (!activity) return;

    const current = (resource.data as Activity[] | undefined) ?? [];
    if (action === "add") {
      resource.data = [...current, activity];
    } else if (action === "delete") {
      resource.data = current.filter((a) => a.key !== activity.key);
    } else {
      resource.data = current.map((a) =>
        a.key === activity.key ? activity : a
      );
    }
  };

  const onDocUpdate = () => resource.reload();
  onMounted(() => {
    socket.emit("doc_subscribe", doctype, docname); // subscribes to doc updates for this doctype:docname
    socket.on("docinfo_update", onUpdate); // subscribes to live communications, comments, likes, assignments, attachments
    socket.on("doc_update", onDocUpdate); // subscribes to field changes
  });
  onUnmounted(() => {
    socket.emit("doc_unsubscribe", doctype, docname);
    socket.off("docinfo_update", onUpdate);
    socket.off("doc_update", onDocUpdate);
  });
}

// (assignee bolding is backend-supplied, so live assignment rows bold only the actor.)
function normalizeLiveActivity(
  key: string,
  doc: Record<string, unknown>,
  resolveAuthor: (email: string | undefined, fallback: UserInfo) => UserInfo
): Activity | null {
  const timestamp = String(doc.creation);
  const actorEmail = (doc.comment_email as string) || (doc.owner as string);
  const author = resolveAuthor(actorEmail, {
    email: actorEmail,
    fullname: (doc.comment_by as string) || actorEmail,
  });
  const name = doc.name as string;

  switch (key) {
    case "comments":
      return {
        type: "comment",
        key: `comment:${name}`,
        timestamp,
        author,
        data: { name, content: doc.content as string },
      };

    case "like_logs":
      return {
        type: "log",
        key: `log:${name}`,
        timestamp,
        author,
        data: {
          name,
          subtype: "like",
          icon: "heart",
          text: `${author.fullname} liked`,
        },
      };

    case "assignment_logs": {
      const isCompleted = doc.comment_type === "Assignment Completed";
      const text = stripHtml(String(doc.content ?? ""));
      // mirror the backend so the assignee bolds on live rows too (not just the actor)
      const assignee = getAssignee(text, String(doc.comment_type ?? ""));
      return {
        type: "log",
        key: `log:${name}`,
        timestamp,
        author,
        data: {
          name,
          subtype: isCompleted ? "assignment_completed" : "assigned",
          icon: isCompleted ? "circle-check" : "user-plus",
          text,
          // additive, like the backend: only present when an assignee was found
          ...(assignee ? { assignee } : {}),
        },
      };
    }

    case "attachment_logs": {
      const isRemoved = doc.comment_type === "Attachment Removed";
      const content = String(doc.content ?? "");
      const href = content.match(/href=['"]([^'"]+)['"]/);
      const fileUrl = !isRemoved && href ? href[1] : undefined;
      return {
        type: "attachment_log",
        key: `attachment:${name}`,
        timestamp,
        author,
        data: {
          name,
          action: isRemoved ? "removed" : "added",
          fileName: stripHtml(content),
          // private files live under /private/… — stabler than the `fa-lock` icon
          isPrivate: fileUrl?.startsWith("/private/") ?? false,
          ...(fileUrl ? { fileUrl } : {}),
        },
      };
    }

    case "communications":
      return {
        type: "email",
        key: `email:${name}`,
        timestamp: String(doc.communication_date || doc.creation),
        author: resolveAuthor(doc.sender as string, {
          email: doc.sender as string,
          fullname: (doc.sender_full_name || doc.sender) as string,
        }),
        data: {
          name,
          subject: doc.subject as string,
          sender: doc.sender as string,
          to: doc.recipients as string,
          cc: doc.cc as string,
          bcc: doc.bcc as string,
          content: doc.content as string,
          deliveryStatus: doc.delivery_status as string,
          attachments: [],
        },
      };

    default:
      return null;
  }
}

function dropDuplicateKeys(activities: Activity[]): Activity[] {
  const uniqueActivities = new Set<string>();
  return activities.filter((a) =>
    uniqueActivities.has(a.key) ? false : uniqueActivities.add(a.key)
  );
}

function compareActivities(
  a: Pick<Activity, "timestamp" | "key">,
  b: Pick<Activity, "timestamp" | "key">
): number {
  return (
    timeValue(a.timestamp) - timeValue(b.timestamp) ||
    a.key.localeCompare(b.key)
  );
}

// Frappe timestamps use a space separator; Date.parse needs 'T' for reliable parsing.
function timeValue(ts?: string): number {
  if (!ts) return 0;
  const t = Date.parse(ts.includes(" ") ? ts.replace(" ", "T") : ts);
  return Number.isNaN(t) ? 0 : t;
}

// Split a run when consecutive rows are >15m apart, so unrelated edit sessions
// don't fold together. (A single save writes all its fields at one timestamp, so
// this only ever splits between distinct saves — never within one.)
const VERSION_FOLD_MAX_GAP_MS = 15 * 60 * 1000;

// True when `next` is close enough to `prev` (within the version-fold gap) to stay
// in the same run; a missing timestamp never splits.
function withinGap(prev: Activity, next: Activity): boolean {
  if (!prev.timestamp || !next.timestamp) return true;
  return (
    Math.abs(timeValue(next.timestamp) - timeValue(prev.timestamp)) <=
    VERSION_FOLD_MAX_GAP_MS
  );
}

// All consecutive-run grouping passes, in order: version folding, then assignment folding.
function groupActivities(activities: Activity[]): Activity[] {
  let _activities = groupVersionActivities(activities);
  _activities = groupAssignmentActivities(_activities);
  return _activities;
}

// Fold each run of consecutive same-author version rows into one summary; others pass through.
export function groupVersionActivities(activities: Activity[]): Activity[] {
  return groupActivityByOwner(
    activities,
    (a): a is VersionActivity => a.type === "version",
    (run) => {
      const summary = summarizeVersions(run);
      return summary ? [summary] : [];
    },
    true // group by time gap too
  );
}

function groupActivityByOwner<T extends Activity>(
  activities: Activity[],
  isMember: (a: Activity) => a is T,
  summarize: (run: T[]) => Activity[],
  groupByTime = false
): Activity[] {
  const out: Activity[] = [];
  let runStart = 0;
  while (runStart < activities.length) {
    const first = activities[runStart];
    if (!isMember(first)) {
      out.push(first);
      runStart++;
      continue;
    }
    let runEnd = runStart + 1;
    while (
      runEnd < activities.length &&
      isMember(activities[runEnd]) &&
      activities[runEnd].author?.email === first.author?.email &&
      (!groupByTime || withinGap(activities[runEnd - 1], activities[runEnd]))
    ) {
      runEnd++;
    }
    out.push(...summarize(activities.slice(runStart, runEnd) as T[]));
    runStart = runEnd;
  }
  return out;
}

// Collapse a run's changes into one summary row carrying a `group` of net changes;
// e.g. status Open→InProgress→Closed becomes status Open→Closed (with full history).
function summarizeVersions(
  versions: VersionActivity[]
): VersionActivity | null {
  const changes: VersionChange[] = []; // one net change per field, in first-seen order
  const byField = new Map<string, { change: VersionChange; index: number }>();

  for (const row of versions) {
    const change = row.data;
    // doc-level rows have no fieldname — never collapse
    if (!change.fieldname) {
      changes.push({ ...change, timestamp: row.timestamp });
      continue;
    }

    const seen = byField.get(change.fieldname);
    if (!seen) {
      const seeded: VersionChange =
        change.type === "diff"
          ? {
              ...change,
              timestamp: row.timestamp,
              history: [
                {
                  from: change.from ?? "",
                  to: change.to,
                  timestamp: row.timestamp,
                },
              ],
            }
          : { ...change, timestamp: row.timestamp };
      byField.set(change.fieldname, { change: seeded, index: changes.length });
      changes.push(seeded);
    } else if (seen.change.type === "diff" && change.type === "diff") {
      // advance the net "to" (keep the first row's "from") and record the hop + newest time
      seen.change.to = change.to;
      seen.change.timestamp = row.timestamp;
      seen.change.history = [
        ...(seen.change.history ?? []),
        { from: change.from ?? "", to: change.to, timestamp: row.timestamp },
      ];
    } else {
      // type changed mid-run (e.g. value edited then cleared) — take the latest
      const replacement: VersionChange = {
        ...change,
        timestamp: row.timestamp,
      };
      changes[seen.index] = replacement;
      byField.set(change.fieldname, { change: replacement, index: seen.index });
    }
  }

  // drop fields that churned back to their starting value (net no-op)
  const visible = changes.filter(
    (c) => !(c.type === "diff" && c.from === c.to)
  );
  if (visible.length === 0) return null;

  // net changes list newest-first by each field's latest hop (first-seen order otherwise)
  visible.sort((a, b) => timeValue(a.timestamp) - timeValue(b.timestamp));

  // key off the first row so Vue reuses the item (keeps expanded state); timestamp from last
  const first = versions[0];
  const last = versions[versions.length - 1];
  const data =
    visible.length === 1
      ? { ...visible[0] }
      : { ...visible[0], group: visible };
  return { ...last, key: first.key, data };
}

const ASSIGNMENT_SUBTYPES = new Set(["assigned", "assignment_completed"]);

// Netting identity: the named assignee, else the self-actor (self rows carry no assignee).
const assignmentIdentity = (row: LogActivity): string =>
  row.data.assignee ?? row.author?.fullname ?? "";

// Fold each run of consecutive same-author assignment logs into one row per
// direction (assigned / removed); others pass through.
function groupAssignmentActivities(activities: Activity[]): Activity[] {
  return groupActivityByOwner(
    activities,
    isFoldableAssignment,
    summarizeAssignments
  );
}

// Any assignment log — named or self-(un)assign — is foldable, so a self-assign
// then self-removal nets out just like a named one.
function isFoldableAssignment(a: Activity): a is LogActivity {
  return a.type === "log" && ASSIGNMENT_SUBTYPES.has(a.data.subtype);
}

// Net each identity across the run (+1 assigned, −1 removed, in first-seen order);
// anyone who nets to zero (assigned then removed) is dropped. Emits ≤2 rows per direction.
function summarizeAssignments(run: LogActivity[]): LogActivity[] {
  if (run.length === 1) return run;

  const net = new Map<string, number>(); // Map keeps first-seen order
  for (const row of run) {
    const id = assignmentIdentity(row);
    net.set(
      id,
      (net.get(id) ?? 0) + (row.data.subtype === "assigned" ? 1 : -1)
    );
  }

  return (["assigned", "assignment_completed"] as const).flatMap((subtype) => {
    const want = subtype === "assigned" ? 1 : -1;
    const ids = new Set(
      [...net].filter(([, n]) => Math.sign(n) === want).map(([id]) => id)
    );
    return foldDirection(run, subtype, ids);
  });
}

// Folded rows for one direction. Named survivors merge into one comma-joined row
// (injected into a surviving row's localized text — backend i18n preserved). Self
// rows have no name to anchor on, so they never merge — each passes through as-is.
function foldDirection(
  run: LogActivity[],
  subtype: LogActivity["data"]["subtype"],
  ids: Set<string>
): LogActivity[] {
  if (!ids.size) return [];
  const rows = run.filter(
    (r) => r.data.subtype === subtype && ids.has(assignmentIdentity(r))
  );

  const out: LogActivity[] = [];
  // self (un)assignment: one actor, can't be name-merged — pass through (latest wins)
  const self = rows.filter((r) => !r.data.assignee);
  if (self.length) out.push(self[self.length - 1]);

  const named = rows.filter((r) => r.data.assignee);
  const names = [...new Set(named.map((r) => r.data.assignee!))];
  if (names.length === 1) {
    out.push(named[0]);
  } else if (names.length > 1) {
    const text = named[0].data.text.replace(
      named[0].data.assignee!,
      names.join(", ")
    );
    out.push({
      ...named[named.length - 1],
      key: named[0].key,
      data: { ...named[0].data, text, assignee: undefined, assignees: names },
    });
  }
  return out;
}
