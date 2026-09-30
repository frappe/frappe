import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick } from "vue";
// Through the frontend's link: from inside ui/, frappe-ui resolves nowhere.
import EmailContent from "../../../../../frontend/node_modules/@framework/ui/src/components/ActivityTimeline/EmailContent.vue";

const HOSTILE = `<p style="color: red">Hi</p><img src="x" onerror="alert(1)"><script>alert(2)</script>`;

function innerHTMLOwner(): object {
  let proto: object | null = HTMLDivElement.prototype;
  while (proto && !Object.getOwnPropertyDescriptor(proto, "innerHTML")) {
    proto = Object.getPrototypeOf(proto);
  }
  return proto!;
}

/** Every string the live page parses as HTML while `run` goes. */
async function liveParses(run: () => Promise<void>): Promise<string[]> {
  const owner = innerHTMLOwner();
  const original = Object.getOwnPropertyDescriptor(owner, "innerHTML")!;
  const parsed: string[] = [];
  Object.defineProperty(owner, "innerHTML", {
    ...original,
    set(this: Element, value: string) {
      if (this.ownerDocument === document) parsed.push(value);
      original.set!.call(this, value);
    },
  });
  try {
    await run();
  } finally {
    Object.defineProperty(owner, "innerHTML", original);
  }
  return parsed;
}

async function mountEmail(content: string): Promise<HTMLIFrameElement> {
  const root = document.createElement("div");
  document.body.appendChild(root);
  createApp({ render: () => h(EmailContent, { content }) }).mount(root);
  await nextTick();
  return root.querySelector("iframe")!;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("EmailContent", () => {
  it("never parses the email in the live page", async () => {
    const parsed = await liveParses(async () => {
      await mountEmail(HOSTILE);
    });
    expect(parsed.filter((html) => html.includes("onerror"))).toEqual([]);
  });

  it("hands the frame no scripts, no handlers and no inline colors", async () => {
    const srcdoc = (await mountEmail(HOSTILE)).getAttribute("srcdoc")!;
    expect(srcdoc).toContain("<p>Hi</p>");
    expect(srcdoc).not.toContain("onerror");
    expect(srcdoc).not.toContain("alert(2)");
  });
});
