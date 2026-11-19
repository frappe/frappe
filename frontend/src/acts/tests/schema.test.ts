// The checker reads only the keywords acts use, and says what to send instead.
import { describe, expect, it } from "vitest";
import { checkValue, type ActSchema } from "../schema/checkValue";

const open: ActSchema = {
  type: "object",
  properties: {
    doctype: { type: "string", minLength: 1 },
    name: { type: ["string", "null"] },
    scope: { type: "string", enum: ["user", "site"] },
    tags: { type: "array", items: { type: "string" } },
  },
  required: ["doctype"],
  additionalProperties: false,
};

describe("checkValue", () => {
  it("passes a value that fits", () => {
    expect(checkValue(open, { doctype: "ToDo", name: null, scope: "user", tags: ["a"] })).toBeUndefined();
  });

  it.each([
    [{}, "value.doctype is required"],
    [{ doctype: "" }, "value.doctype must not be empty"],
    [{ doctype: 5 }, "value.doctype must be a string"],
    [{ doctype: "ToDo", name: 3 }, "value.name must be a string or a null"],
    [{ doctype: "ToDo", scope: "all" }, 'value.scope must be one of "user", "site"'],
    [{ doctype: "ToDo", tags: ["a", 1] }, "value.tags[1] must be a string"],
    [{ doctype: "ToDo", view: "x" }, "value.view is not a field; use doctype, name, scope, tags"],
    ["ToDo", "value must be an object"],
    [[], "value must be an object"],
    [null, "value must be an object"],
  ])("refuses %j", (value, message) => {
    expect(checkValue(open, value)).toBe(message);
  });

  it("takes a union of an object and a list, checking each by its own keywords", () => {
    const either: ActSchema = { type: ["object", "array"], properties: { a: { type: "string" } }, items: { type: "object" } };
    expect(checkValue(either, { a: "x" })).toBeUndefined();
    expect(checkValue(either, [{}, {}])).toBeUndefined();
    expect(checkValue(either, [{}, 1])).toBe("value[1] must be an object");
    expect(checkValue(either, "x")).toBe("value must be an object or an array");
  });

  it("lets a schema with no keyword accept anything, and checks integers", () => {
    expect(checkValue({}, { any: 1 })).toBeUndefined();
    expect(checkValue({ type: "integer" }, 1.5)).toBe("value must be an integer");
    expect(checkValue({ type: "boolean" }, true)).toBeUndefined();
  });
});
