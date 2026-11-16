// `record.post_comment`: an agent's plain text, escaped into paragraphs, posted through the writer's own send.
import type { ActItem } from "@/acts/dispatcher";
import type { RecordPageApi } from "./types";

/** Posts the comment's HTML and resolves its name; a failure throws. */
export type PostComment = (html: string) => Promise<string>;

export function postCommentItem(post: PostComment): ActItem<RecordPageApi> {
  return {
    name: "post_comment",
    palette: false,
    run: async (_page, value: { content: string }) => {
      const html = commentHtml(value.content);
      if (!html) throw new Error("content has no text");
      const comment = await post(html);
      if (!comment) throw new Error("The comment was not posted");
      return { comment };
    },
  };
}

/** Each non-blank line is a paragraph; the text is escaped, so markup in it stays text. */
export function commentHtml(text: string): string {
  return text
    .split(/\r?\n/)
    .filter((line) => line.trim())
    .map((line) => `<p>${escapeHtml(line)}</p>`)
    .join("");
}

function escapeHtml(text: string) {
  return text.replace(/[&<>"']/g, (char) => ESCAPES[char]);
}

const ESCAPES: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
