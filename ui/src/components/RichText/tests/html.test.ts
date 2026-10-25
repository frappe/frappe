import { describe, expect, it } from "vitest";
import { htmlToText, isEmptyHtml } from "../html";

describe("htmlToText", () => {
  it("breaks lines at blocks and line breaks, and decodes entities", () => {
    const html = "<h2>Plan</h2><p>Fish &amp; chips<br>today</p><ul><li>one</li><li>two</li></ul>";
    expect(htmlToText(html)).toBe("Plan\nFish & chips\ntoday\none\ntwo");
  });

  it("keeps inline marks on their line", () => {
    expect(htmlToText("<p>Hello <b>there</b>&nbsp;now</p>")).toBe("Hello there now");
  });

  it("reads a desk v1 value through its wrapper", () => {
    const html = '<div class="ql-editor read-mode"><p class="ql-indent-1">First</p><p>Second</p></div>';
    expect(htmlToText(html)).toBe("First\nSecond");
  });

  it("is empty for nothing", () => {
    expect(htmlToText(null)).toBe("");
    expect(htmlToText("<p></p>")).toBe("");
  });
});

describe("isEmptyHtml", () => {
  it("is true for an empty block", () => {
    expect(isEmptyHtml("<p></p>")).toBe(true);
    expect(isEmptyHtml("<h2> </h2>")).toBe(true);
  });

  it("is false for an image or a video with no text", () => {
    expect(isEmptyHtml('<p><img src="/files/a.png"></p>')).toBe(false);
    expect(isEmptyHtml('<video src="/files/a.mp4"></video>')).toBe(false);
  });
});
