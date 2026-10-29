import { describe, expect, it } from "vitest";
import { drawCodeBlocks, hasCodeBlock, loadHighlighter } from "../codeBlocks";

function parse(html: string) {
  return new DOMParser().parseFromString(html, "text/html").body;
}

describe("drawCodeBlocks", () => {
  it("numbers each line before the highlighter arrives", () => {
    const body = parse(drawCodeBlocks("<pre><code>a\nb\nc</code></pre>", null));
    const lines = [...body.querySelectorAll("pre.code-block .code-block-lines > span")];
    expect(lines.map((line) => line.textContent)).toEqual(["1", "2", "3"]);
    expect(body.querySelector(".code-block-lines")!.getAttribute("aria-hidden")).toBe("true");
    expect(body.querySelector("code")!.textContent).toBe("a\nb\nc");
  });

  it("highlights a named language and detects an unnamed one", async () => {
    const highlighter = await loadHighlighter();
    const named = parse(
      drawCodeBlocks('<pre><code class="language-javascript">return 1;</code></pre>', highlighter)
    );
    expect(named.querySelector("code .hljs-keyword")!.textContent).toBe("return");
    expect(named.querySelector("code")!.textContent).toBe("return 1;");

    const detected = parse(drawCodeBlocks("<pre><code>SELECT name FROM tabToDo;</code></pre>", highlighter));
    expect(detected.querySelector('code [class^="hljs-"]')).not.toBeNull();
  });

  it("wraps a desk v1 bare pre in code", () => {
    const body = parse(drawCodeBlocks("<pre>x = 1</pre>", null));
    expect(body.querySelector("pre > code")!.textContent).toBe("x = 1");
  });

  it("finds a code block only where a pre is", () => {
    expect(hasCodeBlock("<p>pre-amble</p><pre>x</pre>")).toBe(true);
    expect(hasCodeBlock("<p>pre-amble <code>x</code></p>")).toBe(false);
    expect(hasCodeBlock(null)).toBe(false);
  });
});
