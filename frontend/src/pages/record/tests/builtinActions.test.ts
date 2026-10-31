// The framework's own actions: which ones a right unlocks, where each sits, and what delete and duplicate do.
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/router/routeFor", () => ({
  routeFor: (doctype: string) => ({ name: "list", doctype }),
  routeForNew: (doctype: string, values: Record<string, unknown>) => ({ name: "new-record", doctype, values }),
}));

const { deleteDocument, searchDocuments } = vi.hoisted(() => ({
  deleteDocument: vi.fn(async () => ({ data: "ok" })),
  searchDocuments: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({ deleteDocument, searchDocuments }));

import { headerMenuBuiltins, quickActionBuiltins, type FavouriteState, type FollowState } from "../builtinActions";
import { FILES_TAB, recordTabBuiltins } from "../tabs/recordTabs";
import { assignOptions, type AssignState } from "../assignAct";

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

  it("leads with comment on a record the reader cannot email, opening the comment writer", () => {
    const open = vi.fn();
    const comment = quickActionBuiltins({})[0];
    expect(comment).toMatchObject({ name: "comment", label: "Comment", icon: "lucide-message-square" });
    comment.run!({ composer: { open } } as any);
    expect(open).toHaveBeenCalledWith("comment");
  });

  it("leads with email only with the right, opening the email writer", () => {
    expect(names({ print: 1 })).toEqual(["comment", "print", "copy_link"]);
    expect(names({ email: 1, print: 1 })).toEqual(["email", "comment", "print", "copy_link"]);
    const open = vi.fn();
    const email = quickActionBuiltins({ email: 1 })[0];
    expect(email).toMatchObject({ name: "email", label: "Email", icon: "lucide-mail" });
    email.run!({ composer: { open } } as any);
    expect(open).toHaveBeenCalledWith("email");
  });

  it("seeds attach after comment only with the Files tab's upload, which asks for it on the tab shown", () => {
    const requestUpload = vi.fn();
    const filesCreate = (upload?: () => void) =>
      recordTabBuiltins({ requestUpload: upload }).find((tab) => tab.name === FILES_TAB)!.create;
    const actions = quickActionBuiltins({ email: 1, print: 1 }, true, undefined, filesCreate(requestUpload));
    expect(actions.map((a) => a.name)).toEqual(["email", "comment", "attach", "print", "copy_link"]);
    const without = quickActionBuiltins({ email: 1, print: 1 }, true, undefined, filesCreate());
    expect(without.map((a) => a.name)).toEqual(["email", "comment", "print", "copy_link"]);

    const attach = actions[2];
    expect(attach).toMatchObject({ label: "Attach", icon: "lucide-paperclip" });
    const tabs = { active: "activity", activate: vi.fn() };
    attach.run!({ tabs } as any);
    expect(tabs.activate).not.toHaveBeenCalled();
    expect(tabs.active).toBe("activity");
    expect(requestUpload).toHaveBeenCalledOnce();
  });

  it("keeps the star's and Attach's copies out of the palette, and their own rows in", () => {
    const filesCreate = recordTabBuiltins({ requestUpload: vi.fn() }).find((tab) => tab.name === FILES_TAB)!.create!;
    const attach = quickActionBuiltins({}, true, undefined, filesCreate).find((a) => a.name === "attach")!;
    expect(menuRow({}, "favourite_row").palette).toBe(false);
    expect(filesCreate.palette).toBe(false);
    expect(attach.palette).toBeUndefined();
  });

  it("gives attach the Files tab entry's right, so the two hide together", () => {
    const create = { name: "attach_file", label: "Attach a file", icon: "lucide-paperclip", right: "delete", run: () => {} };
    const attach = quickActionBuiltins({}, true, undefined, create).find((a) => a.name === "attach");
    expect(attach?.right).toBe("delete");
  });

  it("seeds tags with write, only while the record has none", () => {
    expect(names({ write: 1 })).toEqual(["comment", "copy_link", "tags"]);
    expect(names({ write: 1 }, true)).toEqual(["comment", "copy_link"]);
    expect(names({}, false)).toEqual(["comment", "copy_link"]);
    expect(quickActionBuiltins({ write: 1 }).at(-1)).toMatchObject({ tagging: true });
  });

  it("offers Duplicate in the copies band only when told the reader may create", () => {
    expect(menu({ delete: 1 }).map((item) => item.name)).not.toContain("duplicate");
    const rows = headerMenuBuiltins({ delete: 1 }, off, { duplicate: true });
    expect(rows.map((item) => [item.name, item.group])).toEqual([
      ["favourite_row", "favourite_band"],
      ["copy_url", "copies"],
      ["copy_id", "copies"],
      ["duplicate", "copies"],
      ["delete", "danger"],
    ]);
    expect(rows[3]).toMatchObject({ label: "Duplicate", icon: "lucide-copy" });
  });

  it("duplicates by opening the new record page on a copy of this record", async () => {
    const page = fakePage(null);
    const duplicate = headerMenuBuiltins({}, off, { duplicate: true }).find((item) => item.name === "duplicate")!;
    await duplicate.run!(page);
    expect(page.router.push).toHaveBeenCalledWith({
      name: "new-record",
      doctype: "CRM Deal",
      values: { __copy_of: "CRM-DEAL-1" },
    });
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

describe("Assign to…", () => {
  const sarah = { id: "sarah@example.com", name: "Sarah Connor", image: "/files/sarah.png" };
  const assignState = (assignees = [sarah]): AssignState => ({ assignees, assign: vi.fn() });
  const assignRow = (perms: Record<string, any>, state = assignState()) =>
    headerMenuBuiltins(perms, off, { assign: state }).find((item) => item.name === "assign");

  it("sits in its own band above the copies, behind the write right", () => {
    expect(assignRow({})).toMatchObject({ right: "write" });
    const rows = headerMenuBuiltins({ write: 1 }, off, { assign: assignState() });
    expect(rows.map((item) => [item.name, item.group])).toEqual([
      ["favourite_row", "favourite_band"],
      ["assign", "assign_band"],
      ["copy_url", "copies"],
      ["copy_id", "copies"],
    ]);
    expect(rows[1]).toMatchObject({ label: "Assign to…", argument: { label: "Users" } });
  });

  it("lists the server's users with avatars, marks the assigned ones, and adds those it did not return", async () => {
    searchDocuments.mockResolvedValue({
      data: [
        { value: "john@example.com", label: "john@example.com", description: "John Parker" },
        { value: "sarah@example.com", label: "sarah@example.com", description: "Sarah Connor" },
        { value: "bot@example.com", label: "bot@example.com" },
        { value: "ann@example.com", label: "Ann Lee" },
      ],
    });
    const emily = { id: "emily@example.com", name: "Emily Chen" };

    const options = await assignOptions([sarah, emily], "e");

    expect(searchDocuments).toHaveBeenCalledWith("User", expect.objectContaining({ txt: "e" }));
    expect(options).toEqual([
      { value: "john@example.com", label: "John Parker", description: "john@example.com", image: null },
      {
        value: "sarah@example.com",
        label: "Sarah Connor",
        description: "sarah@example.com",
        image: "/files/sarah.png",
        disabled: "Assigned",
      },
      { value: "bot@example.com", label: "bot@example.com", image: null },
      { value: "ann@example.com", label: "Ann Lee", description: "ann@example.com", image: null },
      {
        value: "emily@example.com",
        label: "Emily Chen",
        description: "emily@example.com",
        image: null,
        disabled: "Assigned",
      },
    ]);
  });

  it("assigns the picked user, and says so when run with none", () => {
    const state = assignState();
    const row = assignRow({ write: 1 }, state)!;
    const page = fakePage(true);

    row.run!(page, "john@example.com");
    row.run!(page);

    expect(state.assign).toHaveBeenCalledExactlyOnceWith(page, "john@example.com");
    expect(page.toast.error).toHaveBeenCalledExactlyOnceWith("Pick a user to assign");
  });
});

describe("Rename…", () => {
  const renamePage = (form: Record<string, any> | null, confirmed: true | null = true, meta: any = {}) =>
    ({
      ...fakePage(confirmed),
      meta,
      dialog: { form: vi.fn().mockResolvedValue(form), danger: vi.fn().mockResolvedValue(confirmed) },
      rename: vi.fn().mockResolvedValue("CRM-DEAL-2"),
    }) as any;
  const renameRow = (options: { single?: boolean; rename?: boolean } = { rename: true }) =>
    headerMenuBuiltins({ write: 1 }, off, { assign: { assignees: [], assign: vi.fn() }, ...options }).find(
      (item) => item.name === "rename"
    );

  it("sits under Assign to in its band, behind the write right, only when the doctype allows it", () => {
    const rows = headerMenuBuiltins({ write: 1 }, off, { assign: { assignees: [], assign: vi.fn() }, rename: true });
    expect(rows.map((item) => [item.name, item.group])).toEqual([
      ["favourite_row", "favourite_band"],
      ["assign", "assign_band"],
      ["rename", "assign_band"],
      ["copy_url", "copies"],
      ["copy_id", "copies"],
    ]);
    expect(rows[2]).toMatchObject({ label: "Rename…", icon: "lucide-pencil", right: "write" });
    expect(renameRow({})).toBeUndefined();
    expect(renameRow({ rename: true, single: true })).toBeUndefined();
  });

  it("asks for the new name and Merge, then renames through page.rename", async () => {
    const page = renamePage({ new_name: " CRM-DEAL-2 ", merge: 0 });

    await renameRow()!.run!(page);

    expect(page.dialog.form).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Rename CRM-DEAL-1",
        fields: [
          { fieldname: "new_name", fieldtype: "Data", label: "New Name", reqd: 1 },
          { fieldname: "merge", fieldtype: "Check", label: "Merge with existing" },
        ],
        defaults: { new_name: "CRM-DEAL-1" },
        submitLabel: "Rename",
      })
    );
    expect(page.dialog.danger).not.toHaveBeenCalled();
    expect(page.rename).toHaveBeenCalledExactlyOnceWith("CRM-DEAL-2", { merge: false });
  });

  it("labels the name after the field it is set from", async () => {
    const meta = { autoname: "field:organization_name", fields: [{ fieldname: "organization_name", label: "Organization Name" }] };
    const page = renamePage(null, true, meta);

    await renameRow()!.run!(page);

    expect(page.dialog.form.mock.calls[0][0].fields[0].label).toBe("New Organization Name");
    expect(page.rename).not.toHaveBeenCalled();
  });

  it("merges only after the danger confirm", async () => {
    const declined = renamePage({ new_name: "CRM-DEAL-2", merge: 1 }, null);
    await renameRow()!.run!(declined);
    expect(declined.dialog.danger).toHaveBeenCalledWith({
      title: "Merge into CRM-DEAL-2?",
      message: "CRM-DEAL-1 will be merged into CRM-DEAL-2. This cannot be undone.",
      confirmLabel: "Merge",
    });
    expect(declined.rename).not.toHaveBeenCalled();

    const confirmed = renamePage({ new_name: "CRM-DEAL-2", merge: 1 });
    await renameRow()!.run!(confirmed);
    expect(confirmed.rename).toHaveBeenCalledExactlyOnceWith("CRM-DEAL-2", { merge: true });
  });
});
