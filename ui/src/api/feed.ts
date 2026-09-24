// How a wrapper call feeds the data cache: a ticket when it is sent, the reply once it lands.
import { feedPartWrite, settleTicket, takeTicket } from "../cache";
import { isFeedableQuery } from "../cache/listKey";
import type { Envelope } from "./envelope";
import type { ListQuery } from "./index";
import { feedSafely, request, type HttpMethod, type RequestOptions } from "./request";

type Feed<T> = (ticket: number, envelope: Envelope<T>) => void;

/** The ticket is taken at send time, so the cache orders the reply by when it was asked for. */
export function fed<T>(
  method: HttpMethod,
  path: string,
  options: RequestOptions,
  feed: Feed<T>
): Promise<Envelope<T>> {
  const ticket = takeTicket();
  return fedAfter(ticket, request<T>(method, path, { ...options, ticket }), feed);
}

/** Settles the ticket once the reply, or the failure, has been fed. */
export async function fedAfter<T>(
  ticket: number,
  sending: Promise<Envelope<T>>,
  feed: Feed<T>,
  failed?: (error: unknown) => void
): Promise<Envelope<T>> {
  try {
    const envelope = await sending;
    feedSafely(() => feed(ticket, envelope));
    return envelope;
  } catch (error) {
    if (failed) feedSafely(() => failed(error));
    throw error;
  } finally {
    feedSafely(() => settleTicket(ticket));
  }
}

/** A part write answers with the refreshed part under its own key. */
export function feedPartReply(doctype: string, name: string, part: string): Feed<unknown> {
  return (ticket, envelope) => {
    const reply = envelope.data as Record<string, unknown> | null;
    if (reply && typeof reply === "object" && part in reply) {
      feedPartWrite(ticket, doctype, name, part, reply[part]);
    }
  };
}

export function includeNames(include?: readonly string[] | string): readonly string[] {
  if (typeof include !== "string") return include ?? [];
  return include.split(",").map((part) => part.trim()).filter(Boolean);
}

/** Without `fields` the server sends `name` alone, and the cache orders rows by `modified`. */
export function withModified(query: ListQuery): ListQuery {
  if (!isFeedableQuery(query)) return query;
  const fields = query.fields?.length ? query.fields : ["name"];
  if (fields.includes("*") || fields.includes("modified")) return query;
  return { ...query, fields: [...fields, "modified"] };
}
