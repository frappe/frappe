import { reactive } from "vue";
import { toast } from "frappe-ui";
import { apiUrl, downloadFile, getMeta, runDocumentMethod } from "../../api";
import type { DataImportStatus } from "./types";

type DoctypeDoc = { name: string; fields: any[] } & Record<string, unknown>;

/** The doctype's meta and every child table's, as one flat list the steps read by `name`. */
export const fetchDoctypeBundle = async (doctype: string): Promise<DoctypeDoc[]> => {
  const { data, children } = await getMeta<DoctypeDoc>(doctype, { include: "children" });
  return [data, ...((children as DoctypeDoc[] | undefined) ?? [])];
};

/** The bundle as a reloadable holder; the steps read `fields.data.docs`. */
export const useDoctypeBundle = () => {
  const bundle = reactive({
    data: null as { docs: DoctypeDoc[] } | null,
    loading: false,
    reload: async ({ doctype }: { doctype: string }) => {
      bundle.loading = true;
      try {
        bundle.data = { docs: await fetchDoctypeBundle(doctype) };
      } finally {
        bundle.loading = false;
      }
    },
  });
  return bundle;
};

export const getBadgeColor = (status: DataImportStatus) => {
  const colorMap = {
    Pending: "amber",
    Success: "green",
    "Partial Success": "amber",
    Error: "red",
    "Timed Out": "amber",
  } as const;
  return colorMap[status as DataImportStatus] || "gray";
};

export const fieldsToIgnore = [
  "Section Break",
  "Column Break",
  "Tab Break",
  "HTML",
  "Table",
  "Table MultiSelect",
  "Button",
  "Image",
  "Fold",
  "Heading",
];

export const getChildTableName = (
  doctype: string,
  parentDocType: string,
  docs: any[],
) => {
  let childTableName = "";
  let doctypeFields = docs.filter((doc: any) => {
    return doc.name == parentDocType;
  })[0].fields;

  doctypeFields.forEach((field: any) => {
    if (field.options == doctype) {
      childTableName = field.fieldname;
    }
  });
  return childTableName;
};

export const getPreviewData = (
  importName: string,
  file: string | undefined,
  sheet: string | undefined,
) => {
  return runDocumentMethod(
    "Data Import",
    importName,
    "get_preview_from_template",
    { import_file: file, google_sheets_url: sheet },
    { http: "GET", nullable: true },
  )
    .then(({ data }) => data)
    .catch((error: any) => {
      toast.error(error?.message || String(error));
      console.error("Error fetching preview data:", error);
    });
};


const TEMPLATE_METHOD = "frappe.core.doctype.data_import.data_import.download_template";

export interface TemplateRequest {
  doctype: string;
  /** Fieldnames per doctype, the parent's own and each child table's. */
  exportFields: Record<string, string[]>;
  /** `blank_template`, `5_records` or `all`; the server reads the row limit from it. */
  exportRecords: string;
  fileType?: string;
}

/** Fetch the import template for a doctype and save it to the reader's downloads. */
export const downloadTemplate = async (request: TemplateRequest) => {
  const fileType = request.fileType || "CSV";
  const url = apiUrl(`/method/${TEMPLATE_METHOD}`, {
    doctype: request.doctype,
    export_fields: request.exportFields,
    export_records: request.exportRecords,
    file_type: fileType,
  });
  try {
    const blob = await downloadFile(url);
    saveBlob(blob, `${request.doctype}.${fileType === "CSV" ? "csv" : "xlsx"}`);
  } catch (error: any) {
    toast.error(error?.message || "Could not download the template");
    console.error("Error downloading the import template:", error);
  }
};

// Safari and Firefox start the download after this tick, so revoking the URL here would
// hand them a dead blob and the file would silently never save.
const saveBlob = (blob: Blob, fileName: string) => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 0);
};
