import { afterEach, describe, expect, it } from "vitest";
import { h } from "vue";
import { Profile, ProfileGroup, ProfileRow } from "../index";
import { mount, unmountAll } from "./mount";

afterEach(unmountAll);

describe("Profile parts", () => {
  it("draws a row's label, value and default chevron, and passes the click on", async () => {
    const clicks: number[] = [];
    const root = await mount(ProfileRow, {
      label: "Time Zone",
      value: "Asia/Kolkata",
      icon: "lucide-globe",
      onClick: () => clicks.push(1),
    });

    const row = root.querySelector<HTMLElement>("[data-slot=profile-row]")!;
    expect(row.tagName).toBe("BUTTON");
    expect(
      row.querySelector("[data-slot=profile-row-label]")?.textContent
    ).toBe("Time Zone");
    expect(
      row.querySelector("[data-slot=profile-row-value]")?.textContent?.trim()
    ).toBe("Asia/Kolkata");
    expect(row.querySelector(".lucide-globe")).not.toBeNull();
    expect(row.querySelector(".lucide-chevron-right")).not.toBeNull();

    row.click();
    expect(clicks).toHaveLength(1);
  });

  it("lets the suffix slot replace the chevron", async () => {
    const root = await mount(
      ProfileRow,
      { label: "Theme" },
      { suffix: () => h("i", "x") }
    );

    expect(root.querySelector(".lucide-chevron-right")).toBeNull();
    expect(root.querySelector("i")?.textContent).toBe("x");
  });

  it("frames a header and labelled groups of rows", async () => {
    const root = await mount(
      Profile,
      {},
      {
        header: () => "Jane Doe",
        default: () =>
          h(ProfileGroup, { label: "Settings" }, () => [
            h(ProfileRow, { label: "Email" }),
            h(ProfileRow, { label: "Lists" }),
          ]),
      }
    );

    expect(root.querySelector("[data-slot=profile-header]")?.textContent).toBe(
      "Jane Doe"
    );
    expect(
      root.querySelector("[data-slot=profile-group-label]")?.textContent
    ).toBe("Settings");
    expect(root.querySelectorAll("[data-slot=profile-row]")).toHaveLength(2);
  });
});
