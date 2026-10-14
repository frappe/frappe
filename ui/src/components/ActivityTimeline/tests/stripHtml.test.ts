/**
 * @vitest-environment jsdom
 */

import { describe, expect, it } from "vitest";
import { stripHtml } from "../utils";

describe("stripHtml", () => {
  it("decodes HTML entities", () => {
    expect(stripHtml('<a href="/files/R&amp;D.pdf">R&amp;D.pdf</a>')).toBe("R&D.pdf");
  });
});
