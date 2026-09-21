import { call, toast } from "frappe-ui";
import { apiUrl, downloadFile } from "../../api";
import type { DataImportStatus } from "./types";

export const getBadgeColor = (status: DataImportStatus) => {
  const colorMap = {
    Pending: "orange",
    Success: "green",
    "Partial Success": "orange",
    Error: "red",
    "Timed Out": "orange",
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
  return call(
    "frappe.core.doctype.data_import.data_import.get_preview_from_template",
    {
      data_import: importName,
      import_file: file,
      google_sheets_url: sheet,
    },
  ).catch((error: any) => {
    toast.error(error.messages?.[0] || error);
    console.error("Error fetching preview data:", error);
  });
};


const TEMPLATE_METHOD = "frappe.core.doctype.data_import.data_import.download_template";

export interface TemplateRequest {
  doctype: string;
  /** Fieldnames per doctype, the parent's own and each child table's. */
  exportFields: Record<string, string[]>;
  exportRecords: string;
  fileType?: string;
  /** How many rows of real data to carry; blank for all of them. */
  exportPageLength?: number;
}

/** Fetch the import template for a doctype and save it to the reader's downloads. */
export const downloadTemplate = async (request: TemplateRequest) => {
  const fileType = request.fileType || "CSV";
  const url = apiUrl(`/method/${TEMPLATE_METHOD}`, {
    doctype: request.doctype,
    export_fields: request.exportFields,
    export_records: request.exportRecords,
    file_type: fileType,
    export_page_length: request.exportPageLength,
  });
  try {
    const blob = await downloadFile(url);
    saveBlob(blob, `${request.doctype}.${fileType === "CSV" ? "csv" : "xlsx"}`);
  } catch (error: any) {
    toast.error(error?.message || "Could not download the template");
    console.error("Error downloading the import template:", error);
  }
};

// The object URL holds the blob until it is revoked, so it goes as soon as the click is made.
const saveBlob = (blob: Blob, fileName: string) => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};
