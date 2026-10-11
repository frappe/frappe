import { describe, expect, it } from "vitest";
import { directionFor, nextSort } from "../headerSort";

describe("nextSort", () => {
  it("makes a fresh column the whole sort, ascending", () => {
    const sort = [{ fieldname: "modified", direction: "desc" as const }];
    expect(nextSort(sort, "status")).toEqual([
      { fieldname: "status", direction: "asc" },
    ]);
  });

  it("flips the direction on a second click", () => {
    const asc = nextSort([], "status");
    const desc = nextSort(asc, "status");
    expect(desc).toEqual([{ fieldname: "status", direction: "desc" }]);
    expect(nextSort(desc, "status")).toEqual(asc);
  });

  it("drops the other columns of a multi-column sort", () => {
    const sort = [
      { fieldname: "status", direction: "asc" as const },
      { fieldname: "modified", direction: "desc" as const },
    ];
    expect(nextSort(sort, "modified")).toEqual([
      { fieldname: "modified", direction: "asc" },
    ]);
  });
});

describe("directionFor", () => {
  it("reads the column's direction, or null when it is not sorted", () => {
    const sort = [{ fieldname: "status", direction: "desc" as const }];
    expect(directionFor(sort, "status")).toBe("desc");
    expect(directionFor(sort, "name")).toBeNull();
  });
});
