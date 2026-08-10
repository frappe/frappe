/** Minimal socket.io-compatible listener. Supplied by the host. */
export interface DataImportSocket {
  on: (event: string, handler: (payload: any) => void) => void;
  off: (event: string, handler?: (payload: any) => void) => void;
}

export interface DataImportProps {
  label?: string;
  description?: string;
  doctype?: string | null;
  importName?: string | null;
  doctypeMap?: Record<
    string,
    { title: string; listRoute?: string; pageRoute?: string }
  >;
  /**
   * The app's realtime socket. Given one, the preview table refreshes itself
   * while an import runs. Left out, the user reloads to see progress.
   */
  socket?: DataImportSocket;
}

export interface DataImport {
  name?: string;
  reference_doctype: string;
  import_type: string;
  status: DataImportStatus;
  creation?: string;
  mute_emails: boolean;
  import_file?: string;
  google_sheets_url?: string;
  template_options?: string;
}

/**
 * The slice of frappe-ui's `createListResource` return that these screens use.
 * The paging members are optional so a plain `ListResource` satisfies the type;
 * `hasNextPage` is a boolean on the resource, not the function it was declared
 * as before the move.
 */
export interface DataImports {
  data: DataImport[] | null;
  update: (args: { filters: any[] }) => void;
  insert: {
    submit: (
      params: DataImport,
      options: {
        validate?: () => boolean;
        onSuccess: (data: DataImport) => void;
        onError: (err: any) => void;
      },
    ) => void;
  };
  setValue: {
    submit: (
      params: DataImport,
      options: {
        onSuccess: (data: DataImport) => void;
        onError: (err: any) => void;
      },
    ) => void;
  };
  reload: () => void;
  hasNextPage?: boolean;
  next?: () => void;
}

export type DataImportStatus =
  "Pending" | "Success" | "Partial Success" | "Error" | "Timed Out";

export interface DocField {
  label: string;
  fieldname: string;
  reqd: 0 | 1;
  fieldtype: string;
  options?: string;
}

export interface DocType {
  name: string;
  fields: DocField[];
}

export interface File {
  name: string;
  file_url: string;
  file_name: string;
  file_size: number;
}
