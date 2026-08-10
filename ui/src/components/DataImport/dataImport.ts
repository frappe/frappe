import { call, toast } from "frappe-ui";
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
