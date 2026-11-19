import { describe, expect, it } from "vitest";
import { CHECKBOX_TRACK, columnTracks, MENU_TRACK } from "../columnTracks";

const name = { fieldname: "name", label: "Name" };
const status = { fieldname: "status", label: "Status" };

describe("columnTracks", () => {
  it("leads with the checkbox track and gives the first column a larger share", () => {
    expect(columnTracks([name, status])).toEqual([
      CHECKBOX_TRACK,
      "minmax(0, 2fr)",
      "minmax(0, 1fr)",
    ]);
  });

  it("ends with the menu track when the rows carry a menu", () => {
    expect(columnTracks([name, status], {}, true)).toEqual([
      CHECKBOX_TRACK,
      "minmax(0, 2fr)",
      "minmax(0, 1fr)",
      MENU_TRACK,
    ]);
  });

  it("uses a stored width as a fixed track", () => {
    expect(columnTracks([{ ...name, width: "150px" }, status])).toEqual([
      CHECKBOX_TRACK,
      "150px",
      "minmax(0, 1fr)",
    ]);
  });

  it("adds a filler track when every column is fixed", () => {
    const fixed = [
      { ...name, width: "150px" },
      { ...status, width: "8rem" },
    ];
    expect(columnTracks(fixed)).toEqual([
      CHECKBOX_TRACK,
      "150px",
      "8rem",
      "minmax(0, 1fr)",
    ]);
  });

  it("lets a draft width win over the stored one while dragging", () => {
    const drafts = { name: "210px" };
    expect(columnTracks([{ ...name, width: "150px" }, status], drafts)).toEqual(
      [CHECKBOX_TRACK, "210px", "minmax(0, 1fr)"]
    );
  });
});
