import { afterEach, describe, expect, it } from "vitest";
import { valueControl } from "../valueControl";
import { resetFormatDefaults, setFormatDefaults } from "../../FormLayout/formatDefaults";

afterEach(() => resetFormatDefaults());

describe("a between filter on a date", () => {
  it("shows and reads its range in the user's date format", () => {
    setFormatDefaults({ date_format: "dd-mm-yyyy" });
    const spec = valueControl({
      fieldname: "due",
      operator: "between",
      value: [],
      field: { label: "Due", value: "due", fieldname: "due", fieldtype: "Date" },
    });
    expect(spec).toEqual({ control: "dateRange", props: { iconLeft: "", format: "DD-MM-YYYY" } });
  });
});
