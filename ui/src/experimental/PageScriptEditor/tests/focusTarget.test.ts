import { describe, expect, it } from "vitest";
import { focusableIn } from "../focusTarget";

function marked(html: string) {
  const marker = document.createElement("div");
  marker.setAttribute("autofocus", "");
  marker.innerHTML = html;
  document.body.appendChild(marker);
  return marker;
}

describe("focusableIn", () => {
  it("finds a button that is already there", async () => {
    const marker = marked("<button>New script</button>");
    expect(await focusableIn(marker)).toBe(marker.querySelector("button"));
  });

  it("resolves the marker itself when it is the focusable thing", async () => {
    const marker = marked("");
    marker.setAttribute("contenteditable", "true");
    expect(await focusableIn(marker)).toBe(marker);
  });

  // The whole reason this waits: CodeMirror mounts frames after the branch that
  // holds it, and a single look at the DOM misses it every time.
  it("waits for a target that arrives later", async () => {
    const marker = marked("");
    setTimeout(() => {
      const editor = document.createElement("div");
      editor.setAttribute("contenteditable", "true");
      marker.appendChild(editor);
    }, 30);
    const found = await focusableIn(marker, 2000);
    expect(found).toBe(marker.querySelector("[contenteditable]"));
  });

  it("gives up at the deadline rather than polling forever", async () => {
    const marker = marked("<span>nothing focusable</span>");
    expect(await focusableIn(marker, 20)).toBeNull();
  });

  it("gives up when the marker leaves the document", async () => {
    const marker = marked("<span>nothing focusable yet</span>");
    marker.remove();
    expect(await focusableIn(marker, 2000)).toBeNull();
  });

  // A disabled button is not somewhere focus can land, so it does not count.
  it("ignores a disabled button", async () => {
    const marker = marked("<button disabled>Save</button>");
    expect(await focusableIn(marker, 20)).toBeNull();
  });
});
