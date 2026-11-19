// The reader's follow: the `follows` part, offered under desk v1's gate.
import type { Envelope, Session } from "@framework/ui/api";

/** Desk v1's gate: the doctype tracks changes and the reader asked for follow mails. */
export function canFollow(
  meta: { track_changes?: number | boolean } | null,
  session: Session,
): boolean {
  return (
    Boolean(meta?.track_changes) && Boolean(session.user.document_follow_notify)
  );
}

/** Why the server declined a follow: it answers 200 with the state and says so beside the data. */
export function declinedMessage(answer: Envelope<{ follows?: boolean }>, adding: boolean): string | undefined {
	if (!adding || answer.data.follows) return;
	const [first] = (answer.messages as { message?: string }[] | undefined) ?? [];
	return first?.message;
}
