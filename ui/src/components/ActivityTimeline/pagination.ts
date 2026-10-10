import { createResource } from "frappe-ui";
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
    // unknown until the first page answers; true would flash "load more" over cached rows
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

/**
 * History paging: fetch the next older page of each paged source and append it. The feed
 * re-sorts, so the rows land wherever their timestamps put them.
 */
export function createHistoryPagination(
  doctype: string,
  docname: string,
  resource: ReturnType<typeof createResource>,
  sources: PagedSources
): Pagination {
  const appendToFeed = (olderRows: Activity[]) => {
    const loadedRows = (resource.data as Activity[] | undefined) ?? [];
    resource.data = [...loadedRows, ...olderRows];
  };

  const olderEmails = createResource({
    url: "frappe.desk.form.activity.get_more_email_activities",
    auto: false,
    onSuccess: (response: {
      activities: Activity[];
      has_more_emails?: boolean;
    }) => {
      appendToFeed(response.activities);
      sources.hasMoreEmails.value = !!response.has_more_emails;
    },
  });

  const olderMilestones = createResource({
    url: "frappe.desk.form.activity.get_more_milestone_activities",
    auto: false,
    onSuccess: (response: {
      activities: Activity[];
      has_more_milestones?: boolean;
      next_milestone_start?: number;
    }) => {
      appendToFeed(response.activities);
      sources.hasMoreMilestones.value = !!response.has_more_milestones;
      // backend-supplied: a milestone on a field the user cannot read is counted but not
      // returned, so an offset counted from the rendered rows would skip the rows behind it
      sources.milestoneStart.value =
        response.next_milestone_start ?? sources.milestoneStart.value;
    },
  });

  const isFetching = () => olderEmails.loading || olderMilestones.loading;

  // One control, both sources: a row is older history whichever source it came from.
  const fetchNextPage = () => {
    if (isFetching()) return;
    if (sources.hasMoreEmails.value) {
      const loadedRows = (resource.data as Activity[] | undefined) ?? [];
      // count-based offset: emails are only appended, so the loaded count is the next start
      const loadedEmailCount = loadedRows.filter(
        (row) => row.type === "email"
      ).length;
      olderEmails.submit({ doctype, name: docname, start: loadedEmailCount });
    }
    if (sources.hasMoreMilestones.value) {
      olderMilestones.submit({
        doctype,
        name: docname,
        start: sources.milestoneStart.value,
      });
    }
  };

  // reactive() so the refs unwrap when read through the `paginate` prop.
  return reactive({
    hasNextPage: computed(
      () => sources.hasMoreEmails.value || sources.hasMoreMilestones.value
    ),
    isFetchingNextPage: computed(() => isFetching()),
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
