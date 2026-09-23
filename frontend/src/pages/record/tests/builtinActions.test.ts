// The framework's own actions: which ones a right unlocks, where each sits, and what delete does.
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/router/routeFor", () => ({ routeFor: (doctype: string) => ({ name: "list", doctype }) }));

const { deleteDocument } = vi.hoisted(() => ({ deleteDocument: vi.fn(async () => ({ data: "ok" })) }));
vi.mock("@framework/ui/api", () => ({ deleteDocument }));

import { headerMenuBuiltins, quickActionBuiltins, type FavouriteState, type FollowState } from "../builtinActions";

const names = (perms: Record<string, any>, tagged = false) =>
  quickActionBuiltins(perms, tagged).map((a) => a.name);

const off: FavouriteState = { favourited: false, toggle: vi.fn() };
const menu = (perms: Record<string, any>, favourite = off) => headerMenuBuiltins(perms, favourite);
const menuRow = (perms: Record<string, any>, name: string) => menu(perms).find((item) => item.name === name)!;

function fakePage(confirmed: true | null) {
  return {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    dialog: { danger: vi.fn().mockResolvedValue(confirmed) },
    call: vi.fn().mockResolvedValue(null),
    toast: { success: vi.fn(), error: vi.fn() },
    router: { push: vi.fn().mockResolvedValue(undefined) },
  } as any;
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

describe("quickActionBuiltins", () => {
  it("seeds copy_link always and print only with the right; delete is the header's", () => {
    expect(names({})).toEqual(["comment", "copy_link"]);
    expect(names({ print: 1, delete: 1 })).toEqual(["comment", "print", "copy_link"]);
    expect(menu({}).map((item) => item.name)).toEqual(["favourite_row", "copy_url", "copy_id"]);
    const remove = menuRow({ delete: 1 }, "delete");
    expect(remove).toMatchObject({ name: "delete", label: "Delete", group: "danger" });
    expect(remove.display).toBeUndefined();
  });

  it("never offers delete on a single, whatever the right says", () => {
    const rows = headerMenuBuiltins({ delete: 1 }, off, { single: true }).map((item) => item.name);
    expect(rows).toEqual(["favourite_row", "copy_url", "copy_id"]);
  });

  it("bands the menu: the favourite, the copies, then delete", () => {
    expect(menu({ delete: 1 }).map((item) => item.group)).toEqual([
      "favourite_band",
      "copies",
      "copies",
      "danger",
    ]);
  });

  it("names the favourite row for what the star would do next, and runs the same toggle", () => {
    const toggle = vi.fn();
    const page = fakePage(null);
    const add = headerMenuBuiltins({}, { favourited: false, toggle })[0];
    expect(add).toMatchObject({ label: "Add to favourites", icon: "lucide-star" });
    const remove = headerMenuBuiltins({}, { favourited: true, toggle })[0];
    expect(remove).toMatchObject({ label: "Remove from favourites", icon: "lucide-star-off" });
    remove.run!(page);
    expect(toggle).toHaveBeenCalledWith(page);
  });

  it("seeds follow in both places only when handed a state, worded for what it does next", () => {
    const toggle = vi.fn();
    const page = fakePage(null);
    const off: FollowState = { following: false, toggle };
    const quick = quickActionBuiltins({ write: 1 }, false, off);
    expect(quick.map((a) => a.name)).toEqual(["comment", "copy_link", "follow", "tags"]);
    expect(quick[2]).toMatchObject({ label: "Follow", icon: "lucide-bell" });
    const rows = headerMenuBuiltins({ delete: 1 }, off as any, { follow: off });
    expect(rows.map((item) => [item.name, item.group])).toEqual([
      ["favourite_row", "favourite_band"],
      ["follow_row", "favourite_band"],
      ["copy_url", "copies"],
      ["copy_id", "copies"],
      ["delete", "danger"],
    ]);
    expect(rows[1]).toMatchObject({ label: "Follow", icon: "lucide-bell" });
    rows[1].run!(page);
    expect(toggle).toHaveBeenCalledWith(page);

    const on: FollowState = { following: true, toggle };
    const unfollow = { label: "Unfollow", icon: "lucide-bell-off" };
    expect(quickActionBuiltins({}, false, on)[2]).toMatchObject(unfollow);
    expect(headerMenuBuiltins({}, off as any, { follow: on })[1]).toMatchObject(unfollow);
  });

  it("copies the record's name and says so", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.spyOn(navigator, "clipboard", "get").mockReturnValue({ writeText } as any);
    const page = fakePage(null);
    await menuRow({}, "copy_id").run!(page);
    expect(writeText).toHaveBeenCalledWith("CRM-DEAL-1");
    expect(page.toast.success).toHaveBeenCalledWith("ID copied");
  });

  it("leads with comment on every record, opening the comment writer", () => {
    const open = vi.fn();
    const comment = quickActionBuiltins({})[0];
    expect(comment).toMatchObject({ name: "comment", label: "Comment", icon: "lucide-message-square" });
    comment.run!({ composer: { open } } as any);
    expect(open).toHaveBeenCalledWith("comment");
  });

  it("seeds tags with write, only while the record has none", () => {
    expect(names({ write: 1 })).toEqual(["comment", "copy_link", "tags"]);
    expect(names({ write: 1 }, true)).toEqual(["comment", "copy_link"]);
    expect(names({}, false)).toEqual(["comment", "copy_link"]);
    expect(quickActionBuiltins({ write: 1 }).at(-1)).toMatchObject({ tagging: true });
  });

  it("deletes after a confirmed danger dialog, then leaves for the list", async () => {
    const page = fakePage(true);
    await menuRow({ delete: 1 }, "delete").run!(page);
    expect(deleteDocument).toHaveBeenCalledWith("CRM Deal", "CRM-DEAL-1");
    expect(page.router.push).toHaveBeenCalledWith({ name: "list", doctype: "CRM Deal" });
  });

  it("does nothing when the dialog is dismissed", async () => {
    const page = fakePage(null);
    await menuRow({ delete: 1 }, "delete").run!(page);
    expect(deleteDocument).not.toHaveBeenCalled();
    expect(page.router.push).not.toHaveBeenCalled();
  });

  it("refuses to copy without a clipboard, and keeps the page", async () => {
    vi.spyOn(navigator, "clipboard", "get").mockReturnValue(undefined as any);
    const page = fakePage(null);
    await quickActionBuiltins({})[1].run!(page);
    expect(page.toast.error).toHaveBeenCalledWith("Copying needs a secure connection");
  });

  it("opens desk v1's print view for the record", () => {
    const open = vi.spyOn(window, "open").mockReturnValue(null);
    quickActionBuiltins({ print: 1 })[1].run!(fakePage(null));
    expect(open).toHaveBeenCalledWith("/printview?doctype=CRM+Deal&name=CRM-DEAL-1", "_blank");
  });

  it("copies the page address and says so", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.spyOn(navigator, "clipboard", "get").mockReturnValue({ writeText } as any);
    const page = fakePage(null);
    await quickActionBuiltins({})[1].run!(page);
    expect(writeText).toHaveBeenCalledWith(window.location.href);
    expect(page.toast.success).toHaveBeenCalledWith("Link copied");
  });
});
