// `header.amend`: the solid button on a cancelled record, "Open amendment" once the record has one.
import { runMethod } from "@framework/ui/api";
import { __ } from "@/i18n";
import { AMEND_OF } from "@/newRecordValues";
import type { HeaderItem, RecordPageApi } from "@/recordPage";
import { routeFor, routeForNew } from "@/router/routeFor";

const CANCELLED = 2;
const IS_AMENDED = "frappe.client.is_document_amended";

/** Whether the amend act is open to this record: cancelled, with the field the amendment links by. */
export function amendable(doc: Record<string, any>, meta: { fields?: { fieldname: string }[] } | null) {
  return doc.docstatus === CANCELLED && Boolean(meta?.fields?.some((f) => f.fieldname === "amended_from"));
}

/** The record amending this one, or `null`. */
export async function amendmentOf(doctype: string, name: string): Promise<string | null> {
  // `nullable`: the server answers an unamended record with an empty body.
  const { data } = await runMethod<string | false>(
    IS_AMENDED,
    { doctype, docname: name },
    { http: "GET", nullable: true }
  );
  return data || null;
}

/** `amendment` is the lookup's answer; the act waits for it so its label is never wrong. */
export function amendItem(amendment: string | null): HeaderItem {
  return {
    name: "amend",
    label: amendment ? __("Open amendment") : __("Amend"),
    display: "button",
    right: "amend",
    props: { variant: "solid" },
    run: (page: RecordPageApi) =>
      page.router.push(
        amendment ? routeFor(page.doctype, amendment) : routeForNew(page.doctype, { [AMEND_OF]: page.docname })
      ),
  };
}
