import { describe, expect, it } from "vitest";
import { stripEmailColors } from "../utils";

const html =
  '<style>p{margin:0}</style><table bgcolor="red"><tr><td style="color: red; padding: 4px">' +
  '<font color="blue">hi</font></td></tr></table><p style="background-color: #fff">x</p>';

describe("stripEmailColors", () => {
  it("edits a parsed document in place", () => {
    const doc = new DOMParser().parseFromString(html, "text/html");
    expect(stripEmailColors(doc)).toBeUndefined();
    expect(doc.querySelector("table")!.hasAttribute("bgcolor")).toBe(false);
    expect(doc.querySelector("td")!.getAttribute("style")).toBe("padding: 4px");
    expect(doc.querySelector("font")!.hasAttribute("color")).toBe(false);
    expect(doc.querySelector("p")!.hasAttribute("style")).toBe(false);
  });

  // Deprecated, for an app built on develop: html in, stripped html out.
  it("still takes an html string and returns the stripped html", () => {
    const out = stripEmailColors(html);
    expect(out).toBe(
      "<style>p{margin:0}</style><table><tr><td style=\"padding: 4px\"><font>hi</font></td></tr></table><p>x</p>"
    );
  });

  it("returns an empty string unchanged", () => {
    expect(stripEmailColors("")).toBe("");
  });

  it("passes a missing string through, as develop did", () => {
    expect(stripEmailColors(undefined as unknown as string)).toBeUndefined();
    expect(stripEmailColors(null as unknown as string)).toBeNull();
  });
});
