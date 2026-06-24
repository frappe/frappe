import { createResource } from "frappe-ui";
import { computed } from "vue";
import type { Activity, VersionActivity } from "./types";

const resources = new Map<string, ReturnType<typeof createResource>>();

export function useActivityTimeline(
  doctype: string,
  docname: string,
  order: "asc" | "desc" = "desc"
) {
  const key = `${doctype}:${docname}`;
  let resource = resources.get(key);
  if (!resource) {
    resource = createResource({
      url: "frappe.desk.form.activity.get_activity_timeline",
      params: { doctype, name: docname },
      cache: `activities:${key}`,
      auto: true,
    });
    resources.set(key, resource);
  }

  return {
    activities: computed<Activity[]>(() => {
      const list = [...((resource.data as Activity[]) || [])];
      list.sort(compareActivities);
      const grouped = groupConsecutiveVersions(list);
      return order === "desc" ? grouped.reverse() : grouped;
    }),
    loading: computed<boolean>(() => resource.loading),
    error: computed(() => resource.error || null),
    reload: () => resource.reload(),
  };
}

export function groupConsecutiveVersions(activities: Activity[]): Activity[] {
  const out: Activity[] = [];
  let i = 0;
  while (i < activities.length) {
    const current = activities[i];
    if (current.type !== "version") {
      out.push(current);
      i++;
      continue;
    }
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
      const cur = current as VersionActivity;
      out.push({ ...cur, data: { ...cur.data, group: run } });
    }
    i = j;
  }
  return out;
}

function compareActivities(
  a: { timestamp?: string; key: string },
  b: { timestamp?: string; key: string }
): number {
  return timeValue(a.timestamp) - timeValue(b.timestamp) || a.key.localeCompare(b.key);
}

// Frappe timestamps use a space separator; Date.parse needs 'T' for reliable parsing
function timeValue(ts?: string): number {
  if (!ts) return 0;
  const t = Date.parse(ts.includes(" ") ? ts.replace(" ", "T") : ts);
  return Number.isNaN(t) ? 0 : t;
}
