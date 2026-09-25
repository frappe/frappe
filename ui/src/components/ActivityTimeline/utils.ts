import { dayjsLocal } from "frappe-ui";
import { ref, type Ref } from "vue";

export const dateTooltipFormat = "ddd, MMM D, YYYY h:mm A";

export function dateFormat(date?: string, format = dateTooltipFormat): string {
  if (!date) return "";
  return dayjsLocal(date).format(format);
}

export function timeAgo(date?: string): string {
  if (!date) return "";
  return dayjsLocal(date).fromNow();
}

/** Plain text from an HTML fragment (used by the realtime normalizer). */
export function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, "").trim();
}

/** Clip for display; `title` holds the full value only when clipped (tooltip on truncation). */
export function truncate(
  value = "",
  limit = 40
): { text: string; title?: string } {
  if (value.length <= limit) return { text: value };
  return { text: value.slice(0, limit) + "…", title: value };
}

const escapeRegExp = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/**
 * Split `text` into bold/plain segments, bolding each occurrence of `names`.
 * Matches exact backend-supplied strings, so it's locale-agnostic — no template parsing.
 */
export function splitBold(
  text: string,
  names: Array<string | undefined>
): Array<{ text: string; bold: boolean }> {
  // longest first so "Foo Bar" wins over a stray "Foo"
  const unique = [...new Set(names.filter(Boolean) as string[])].sort(
    (a, b) => b.length - a.length
  );
  if (!unique.length) return [{ text, bold: false }];

  const matcher = new RegExp(`(${unique.map(escapeRegExp).join("|")})`, "g");
  const bolded = new Set(unique);
  return text
    .split(matcher)
    .filter((part) => part !== "")
    .map((part) => ({ text: part, bold: bolded.has(part) }));
}

// `{n}` → non-greedy capture; returns { placeholderIndex: value } or null.
function matchFormatTemplate(
  template: string,
  text: string
): Record<number, string> | null {
  const order: number[] = [];
  let pattern = "^";
  for (const part of template.split(/(\{\d+\})/)) {
    const m = /^\{(\d+)\}$/.exec(part);
    if (m) {
      order.push(Number(m[1]));
      pattern += "([\\s\\S]+?)";
    } else {
      pattern += escapeRegExp(part);
    }
  }
  pattern += "$";

  const match = new RegExp(pattern).exec(text);
  if (!match) return null;
  const groups: Record<number, string> = {};
  order.forEach((idx, i) => (groups[idx] = match[i + 1]));
  return groups;
}

// The assignee named in an assignment-log comment, or null. Mirrors the backend's
// `assignee_from_assignment` (todo.py templates); null when the assignee is the actor.
export function getAssignee(text: string, commentType: string): string | null {
  // [template, assignee index | null when it's the actor]; self-assign first.
  const templates: Array<[string, number | null]> =
    commentType === "Assigned"
      ? [
          ["{0} self assigned this task: {1}", null],
          ["{0} assigned {1}: {2}", 1],
        ]
      : [
          ["{0} removed their assignment.", null],
          ["Assignment of {0} removed by {1}", 0],
        ];

  for (const [template, assigneeIdx] of templates) {
    const groups = matchFormatTemplate(template, text);
    if (!groups) continue;
    return assigneeIdx === null ? null : groups[assigneeIdx] ?? null;
  }
  return null;
}

const COLOR_PROPS = new Set([
  "color",
  "background",
  "background-color",
  "border-color",
]);

/** Strip color-related inline styles + bgcolor/color attrs so iframe CSS controls colors. */
export function stripEmailColors(html: string): string {
  if (!html) return html;
  const div = document.createElement("div");
  div.innerHTML = html;

  div.querySelectorAll("[style]").forEach((el) => {
    const filtered = (el.getAttribute("style") || "")
      .split(";")
      .map((s) => s.trim())
      .filter(
        (s) => s && !COLOR_PROPS.has(s.split(":")[0].trim().toLowerCase())
      )
      .join("; ");
    if (filtered) el.setAttribute("style", filtered);
    else el.removeAttribute("style");
  });

  div
    .querySelectorAll("[bgcolor]")
    .forEach((el) => el.removeAttribute("bgcolor"));
  div
    .querySelectorAll("font[color]")
    .forEach((el) => el.removeAttribute("color"));

  return div.innerHTML;
}

// Reactive mirror of <html data-theme>; lazy singleton MutationObserver, shared.
// Unlike frappe-ui's useTheme (a controller), this only observes — never writes.
let dataTheme: Ref<string> | null = null;

export function useDataTheme(): Ref<string> {
  if (!dataTheme) {
    const current = () =>
      document.documentElement.getAttribute("data-theme") || "light";
    dataTheme = ref(current());
    new MutationObserver(() => {
      dataTheme!.value = current();
    }).observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
  }
  return dataTheme;
}

/** Split a comma-separated recipients string, respecting quoted display names. */
export function splitRecipients(
  field: string | string[],
  valuesToExclude: string[] = []
): string[] {
  if (Array.isArray(field)) {
    return field.filter(Boolean).filter((v) => !valuesToExclude.includes(v));
  }

  const parts: string[] = [];
  let current = "";
  let inQuotes = false;
  for (const char of field) {
    if (char === '"') {
      inQuotes = !inQuotes;
      current += char;
    } else if (char === "," && !inQuotes) {
      parts.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  if (current) parts.push(current.trim());

  return parts.filter(Boolean).filter((v) => !valuesToExclude.includes(v));
}

/**
 * Clone host stylesheets into the iframe head so emails inherit app styling.
 * External sheets load async; `onAsyncLoad` (height re-measure) re-runs when each finishes.
 */
export function applyCssToIframe(
  iframe: HTMLIFrameElement,
  onAsyncLoad?: () => void
): void {
  const head = iframe.contentDocument?.head;
  if (!head) return;
  const anchor = head.firstChild;
  document.querySelectorAll('link[rel="stylesheet"], style').forEach((node) => {
    const clone = node.cloneNode(true) as HTMLElement;
    if (clone.tagName === "LINK" && onAsyncLoad) {
      clone.addEventListener("load", onAsyncLoad);
    }
    head.insertBefore(clone, anchor);
  });
}
