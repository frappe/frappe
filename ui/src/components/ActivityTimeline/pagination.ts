import { runMethod } from "../../api";
import { computed, reactive, ref, type Ref } from "vue";
import type { Activity, CustomActivity, Pagination } from "./types";

/** How far back each paged source has been read; everything else arrives whole on first load. */
export interface PagedSources {
  hasMoreEmails: Ref<boolean>;
  hasMoreMilestones: Ref<boolean>;
  milestoneStart: Ref<number>;
}

/** The paging numbers a first-page response carries next to its rows. */
export interface FirstPageResponse {
  has_more_emails?: boolean;
  has_more_milestones?: boolean;
  next_milestone_start?: number;
}

export function createPagedSources(): PagedSources {
  return {
    hasMoreEmails: ref(false),
    hasMoreMilestones: ref(false),
    milestoneStart: ref(0),
  };
}

/**
 * Takes the paging numbers off a first-page response. Once the user has paged past it those
 * older rows are kept across reloads, so page one's flag and offset are stale from then on.
 */
export function applyFirstPage(
  sources: PagedSources,
  response: FirstPageResponse
) {
  sources.hasMoreEmails.value = !!response.has_more_emails;
  if (sources.milestoneStart.value !== 0) return;
  sources.hasMoreMilestones.value = !!response.has_more_milestones;
  sources.milestoneStart.value = response.next_milestone_start ?? 0;
}

// The two paged sources; a reload re-appends the older pages of these already loaded.
export function isPagedRow(activity: Activity | CustomActivity): boolean {
  if (activity.type === "email") return true;
  if (activity.type !== "log") return false;
  return (
    (activity.data as { subtype?: string } | null)?.subtype === "milestone"
  );
}

/** @deprecated Calls `get_more_*` endpoints that desk v2 does not serve; v2 pages by cursor. */
export function createHistoryPagination(
  doctype: string,
  docname: string,
  resource: { data?: unknown },
  sources: PagedSources
): Pagination {
  const loading = ref(false);
  const loadedRows = () => (resource.data as Activity[] | undefined) ?? [];
  const appendToFeed = (olderRows: Activity[]) => {
    resource.data = [...loadedRows(), ...olderRows];
  };

  const fetchOlderEmails = async () => {
    // count-based offset: emails are only appended, so the loaded count is the next start
    const start = loadedRows().filter((row) => row.type === "email").length;
    const { data } = await runMethod<{
      activities: Activity[];
      has_more_emails?: boolean;
    }>("frappe.desk.form.activity.get_more_email_activities", {
      doctype,
      name: docname,
      start,
    });
    appendToFeed(data.activities);
    sources.hasMoreEmails.value = !!data.has_more_emails;
  };

  const fetchOlderMilestones = async () => {
    const { data } = await runMethod<{
      activities: Activity[];
      has_more_milestones?: boolean;
      next_milestone_start?: number;
    }>("frappe.desk.form.activity.get_more_milestone_activities", {
      doctype,
      name: docname,
      start: sources.milestoneStart.value,
    });
    appendToFeed(data.activities);
    sources.hasMoreMilestones.value = !!data.has_more_milestones;
    // backend-supplied: a milestone on a field the user cannot read is counted but not
    // returned, so an offset counted from the rendered rows would skip the rows behind it
    sources.milestoneStart.value =
      data.next_milestone_start ?? sources.milestoneStart.value;
  };

  // One control, both sources: a row is older history whichever source it came from.
  const fetchNextPage = async () => {
    if (loading.value) return;
    loading.value = true;
    try {
      await Promise.all([
        sources.hasMoreEmails.value && fetchOlderEmails(),
        sources.hasMoreMilestones.value && fetchOlderMilestones(),
      ]);
    } finally {
      loading.value = false;
    }
  };

  // reactive() so the refs unwrap when read through the `paginate` prop.
  return reactive({
    hasNextPage: computed(
      () => sources.hasMoreEmails.value || sources.hasMoreMilestones.value
    ),
    isFetchingNextPage: computed(() => loading.value),
    fetchNextPage,
    isPagedRow,
    // in-feed row above the oldest paged row; the copy lives here, not in the component
    loadMore: {
      position: "inline" as const,
      label: "Show previous activity",
      icon: "lucide-chevrons-up",
    },
  });
}
