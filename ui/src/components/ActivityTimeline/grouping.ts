// Pure, frappe-ui-free timeline shaping: dedupe, sort, and the consecutive-run
// folding (version summaries + assignment netting) the `activities` computed runs
// over the fetched feed. No resource/socket imports so the logic stays unit-testable
// in isolation.
import type {
  Activity,
  LogActivity,
  VersionActivity,
  VersionChange,
} from "./types";

export function dropDuplicateKeys(activities: Activity[]): Activity[] {
  const uniqueActivities = new Set<string>();
  return activities.filter((a) =>
    uniqueActivities.has(a.key) ? false : uniqueActivities.add(a.key)
  );
}

export function compareActivities(
  a: Pick<Activity, "timestamp" | "key">,
  b: Pick<Activity, "timestamp" | "key">
): number {
  return (
    timeValue(a.timestamp) - timeValue(b.timestamp) ||
    a.key.localeCompare(b.key)
  );
}

// Frappe timestamps use a space separator; Date.parse needs 'T' for reliable parsing.
export function timeValue(ts?: string): number {
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
export function groupActivities(activities: Activity[]): Activity[] {
  let _activities = groupVersionActivities(activities);
  _activities = groupAssignmentActivities(_activities);
  return _activities;
}

// Fold same-author version rows chained ≤15m apart into one summary, regardless of
// interleaved rows — an activity log or comment between two saves must not split a
// fold. The summary sits where the cluster's last row was, so order stays chronological.
export function groupVersionActivities(activities: Activity[]): Activity[] {
  interface Cluster {
    rows: VersionActivity[];
    lastIndex: number;
  }
  const open = new Map<string, Cluster>(); // author email → growing cluster
  const clusterAt = new Map<number, Cluster>(); // index of a cluster's last row
  activities.forEach((a, i) => {
    if (a.type !== "version") return;
    const author = a.author?.email ?? "";
    const cluster = open.get(author);
    if (cluster && withinGap(cluster.rows[cluster.rows.length - 1], a)) {
      clusterAt.delete(cluster.lastIndex);
      cluster.rows.push(a);
      cluster.lastIndex = i;
      clusterAt.set(i, cluster);
    } else {
      const started = { rows: [a], lastIndex: i };
      open.set(author, started);
      clusterAt.set(i, started);
    }
  });

  const out: Activity[] = [];
  activities.forEach((a, i) => {
    if (a.type !== "version") {
      out.push(a);
      return;
    }
    const cluster = clusterAt.get(i);
    if (!cluster) return; // folded into a later row of its cluster
    const summary = summarizeVersions(cluster.rows);
    if (summary) out.push(summary);
  });
  return out;
}

function groupActivityByOwner<T extends Activity>(
  activities: Activity[],
  isMember: (a: Activity) => a is T,
  summarize: (run: T[]) => Activity[]
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
      activities[runEnd].author?.email === first.author?.email
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
export function summarizeVersions(
  versions: VersionActivity[]
): VersionActivity | null {
  const changes: VersionChange[] = []; // one net change per field, in first-seen order
  const byField = new Map<string, VersionChange>();

  for (const row of versions) {
    const change = row.data;
    // doc-level rows have no fieldname — never collapse
    if (!change.fieldname) {
      changes.push({ ...change, timestamp: row.timestamp });
      continue;
    }

    const seen = byField.get(change.fieldname);
    if (seen && seen.type === "diff" && change.type === "diff") {
      // advance the net "to" (keep the first row's "from") and record the hop + newest time
      seen.to = change.to;
      seen.timestamp = row.timestamp;
      seen.history = [
        ...(seen.history ?? []),
        { from: change.from ?? "", to: change.to, timestamp: row.timestamp },
      ];
    } else {
      // first change for this field — or its kind changed mid-run (edited then
      // cleared): keep the earlier entry and start a new one, so nothing is erased
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
      byField.set(change.fieldname, seeded);
      changes.push(seeded);
    }
  }

  // net no-ops (Bug → Incident → Bug) stay visible; the chevron shows the round trip
  if (changes.length === 0) return null;

  // net changes list oldest-first by each field's latest hop (first-seen order otherwise)
  changes.sort((a, b) => timeValue(a.timestamp) - timeValue(b.timestamp));

  // key off the first row so Vue reuses the item (keeps expanded state); timestamp from last
  const first = versions[0];
  const last = versions[versions.length - 1];
  const data =
    changes.length === 1
      ? { ...changes[0] }
      : { ...changes[0], group: changes };
  return { ...last, key: first.key, data };
}

const ASSIGNMENT_SUBTYPES = new Set(["assigned", "assignment_completed"]);

// Netting identity: the named assignee, else the self-actor (self rows carry no assignee).
const assignmentIdentity = (row: LogActivity): string =>
  row.data.assignee ?? row.author?.fullname ?? "";

// Fold each run of consecutive same-author assignment logs into one row per
// direction (assigned / removed); others pass through.
export function groupAssignmentActivities(activities: Activity[]): Activity[] {
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
export function summarizeAssignments(run: LogActivity[]): LogActivity[] {
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
