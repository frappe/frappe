import { createResource } from "frappe-ui";
import { computed } from "vue";
import type { Activity, VersionActivity } from "./types";

// Parse a Frappe (YYYY-MM-DD HH:mm:ss.ffffff), ISO, or other Date-parseable
// timestamp to a comparable epoch. Missing/invalid → 0. More forgiving than a
// string localeCompare, so rows with ISO/Date timestamps still sort.
function timeValue(ts?: string): number {
  if (!ts) return 0;
  // frappe separates date & time with a space; ISO needs a 'T' for reliable parsing
  const t = Date.parse(ts.includes(" ") ? ts.replace(" ", "T") : ts);
  return Number.isNaN(t) ? 0 : t;
}

// chronological comparator with a stable `key` tiebreak. The endpoint already
// returns ascending order; we re-sort defensively so grouping stays correct even
// if a row carries an ISO/Date timestamp the server's lexicographic sort ordered
// differently.
function compareActivities(
  a: { timestamp?: string; key: string },
  b: { timestamp?: string; key: string }
): number {
  return (
    timeValue(a.timestamp) - timeValue(b.timestamp) || a.key.localeCompare(b.key)
  );
}

// One resource per doctype:docname. The endpoint returns the fully-normalized,
// chronologically-ascending activity list under "message", so the default
// frappe-ui fetcher works — no custom fetcher, no client-side parsing.
const resources = new Map<string, ReturnType<typeof createResource>>();

function getResource(doctype: string, docname: string) {
  const key = `${doctype}:${docname}`;
  let resource = resources.get(key);
  if (!resource) {
    resource = createResource({
      url: "frappe.desk.form.activity.get_activity_timeline",
      params: { doctype, name: docname },
      cache: `activities:${key}`, // separate cache entries per doc
      auto: true,
    });
    resources.set(key, resource);
  }
  return resource;
}

/**
 * Fetches a document's normalized activity feed and exposes it as one
 * chronologically sorted list. The shared endpoint
 * (`frappe.desk.form.load.get_activity_timeline`) does all the work — emails,
 * comments, attachment logs, audit lines and field-change history are bucketed,
 * HTML-stripped and label/permission-resolved server-side — so this composable
 * is a thin sorter: it groups consecutive same-author version rows and applies
 * the display order. Fetched once per doctype/docname per session; revisiting a
 * doc reuses the cached data. Call reload() to refresh.
 *
 * Args are plain strings, bound once — to show a different doc, remount the
 * consuming component (e.g. with a :key).
 *
 * This is the data layer, decoupled from the (presentational) ActivityTimeline
 * component. It owns the display order, so the renderer receives the list ready
 * to show. Wire them together at the call site so the renderer never needs to
 * know about doctype/docname:
 *
 *   const { activities, loading, error, reload } =
 *     useActivityTimeline("HD Ticket", "37422", "asc")
 *   <ActivityTimeline :activities="activities" :loading="loading" :error="error" />
 */
export function useActivityTimeline(
  doctype: string,
  docname: string,
  order: "asc" | "desc" = "desc"
) {
  const resource = getResource(doctype, docname);

  return {
    activities: computed<Activity[]>(() => {
      const list = [...((resource.data as Activity[]) || [])];

      // sort (forgiving comparator), group adjacent same-author versions on the
      // ascending list, then apply display order
      list.sort(compareActivities);
      const grouped = groupConsecutiveVersions(list);
      return order === "desc" ? grouped.reverse() : grouped;
    }),
    loading: computed<boolean>(() => resource.loading),
    error: computed(() => resource.error || null),
    reload: () => resource.reload(),
  };
}

// Fold runs of CONSECUTIVE same-author version rows into one VersionActivity
// (their changes concatenated). Operates on an already-sorted list; any
// non-version item — or a version by a different author — breaks the run.
// Runs of length 1 and non-version items pass through unchanged.
export function groupConsecutiveVersions(
  activities: Activity[]
): Activity[] {
  const out: Activity[] = [];
  let i = 0;
  while (i < activities.length) {
    const current = activities[i];
    if (current.type !== "version") {
      out.push(current);
      i++;
      continue;
    }
    // start a run of consecutive same-author versions
    let j = i + 1;
    while (
      j < activities.length &&
      activities[j].type === "version" &&
      activities[j].author?.fullname === current.author?.fullname
    ) {
      j++;
    }
    if (j - i === 1) {
      out.push(current);
    } else {
      const run = activities.slice(i, j) as VersionActivity[];
      // grouped header: keep the first item's identity, attach the run as members
      const cur = current as VersionActivity;
      out.push({ ...cur, data: { ...cur.data, group: run } });
    }
    i = j;
  }
  return out;
}
