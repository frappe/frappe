import { createListResource } from "frappe-ui";
import { computed, ref, watch } from "vue";
import type { DataImportDoc, DataImportStatus } from "./types";

export type DataImportListRow = Pick<
  DataImportDoc,
  | "reference_doctype"
  | "import_type"
  | "status"
  | "creation"
  | "mute_emails"
  | "import_file"
  | "google_sheets_url"
  | "template_options"
> & { name: string };

export type DataImportListStatus = "All" | DataImportStatus;

export function useDataImportList(
  options: { doctype?: string; status?: DataImportListStatus } = {}
) {
  const search = ref("");
  const status = ref<DataImportListStatus>(options.status ?? "All");

  function filters() {
    return [
      options.doctype ? [["reference_doctype", "=", options.doctype]] : [],
      search.value ? [["name", "like", `%${search.value}%`]] : [],
      status.value !== "All" ? [["status", "=", status.value]] : [],
    ].flat();
  }

  const resource = createListResource({
    doctype: "Data Import",
    fields: [
      "name",
      "reference_doctype",
      "import_type",
      "status",
      "creation",
      "mute_emails",
      "import_file",
      "google_sheets_url",
      "template_options",
    ],
    filters: filters(),
    orderBy: "modified desc",
    auto: true,
  });

  // start: 0 drops the pages loaded so far, so a new search begins at the top.
  watch([search, status], () => {
    resource.update({ filters: filters(), start: 0 });
    resource.list.fetch();
  });

  return {
    search,
    status,
    rows: computed(() => (resource.data ?? []) as DataImportListRow[]),
    loading: computed(() => Boolean(resource.list.loading)),
    hasNextPage: computed(() => Boolean(resource.hasNextPage)),
    loadMore: () => resource.next(),
    reload: () => resource.reload(),
  };
}

export type UseDataImportList = ReturnType<typeof useDataImportList>;
