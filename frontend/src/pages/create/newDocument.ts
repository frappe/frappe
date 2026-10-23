// The server's new document for a doctype: its defaults for this user and today.
import { runMethod } from "@framework/ui/api";

const GET_NEW_DOC = "frappe.desk.form.load.get_new_doc";

export async function fetchNewDocument(doctype: string): Promise<Record<string, any>> {
	const { data } = await runMethod<Record<string, any>>(GET_NEW_DOC, { doctype }, { http: "GET" });
	return data;
}
