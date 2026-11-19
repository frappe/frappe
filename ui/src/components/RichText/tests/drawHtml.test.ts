import { describe, expect, it } from "vitest";
import { drawHtml, hasCodeBlock, loadHighlighter } from "../drawHtml";

function parse(html: string) {
  return new DOMParser().parseFromString(html, "text/html").body;
}

describe("drawHtml", () => {
  it("opens every link in a new tab without a handle back to the desk", () => {
    const body = parse(drawHtml('<p><a href="https://example.com" target="_self">x</a></p>', null));
    const link = body.querySelector("a")!;
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer nofollow");
  });

  it("numbers each line before the highlighter arrives", () => {
    const body = parse(drawHtml("<pre><code>a\nb\nc</code></pre>", null));
    const lines = [...body.querySelectorAll("pre.code-block .code-block-lines > span")];
    expect(lines.map((line) => line.textContent)).toEqual(["1", "2", "3"]);
    expect(body.querySelector(".code-block-lines")!.getAttribute("aria-hidden")).toBe("true");
    expect(body.querySelector("code")!.textContent).toBe("a\nb\nc");
  });

  it("highlights a named language and detects an unnamed one", async () => {
    const highlighter = await loadHighlighter();
    const named = parse(
      drawHtml('<pre><code class="language-javascript">return 1;</code></pre>', highlighter)
    );
    expect(named.querySelector("code .hljs-keyword")!.textContent).toBe("return");
    expect(named.querySelector("code")!.textContent).toBe("return 1;");

    const detected = parse(drawHtml("<pre><code>SELECT name FROM tabToDo;</code></pre>", highlighter));
    expect(detected.querySelector('code [class^="hljs-"]')).not.toBeNull();
  });

  it("wraps a desk v1 bare pre in code", () => {
    const body = parse(drawHtml("<pre>x = 1</pre>", null));
    expect(body.querySelector("pre > code")!.textContent).toBe("x = 1");
  });

  it("finds a code block only where a pre is", () => {
    expect(hasCodeBlock("<p>pre-amble</p><pre>x</pre>")).toBe(true);
    expect(hasCodeBlock("<p>pre-amble <code>x</code></p>")).toBe(false);
    expect(hasCodeBlock(null)).toBe(false);
  });
});
