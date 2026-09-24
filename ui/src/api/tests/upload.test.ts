import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearDataCache, feedRecordRead, readCachedDocument, takeTicket } from "../../cache";
import { attachFile, downloadFile, removeAttachment, uploadFile } from "../index";

class FakeXHR {
  static sent: { url: string; form: FormData; headers: Record<string, string> }[] = [];
  static respond: (index: number) => { status: number; body: unknown } = () => ({
    status: 200,
    body: { data: { name: "file-1", file_url: "/private/files/wrap.txt" } },
  });
  static readonly DONE = 4;
  readyState = 0;
  status = 0;
  responseText = "";
  upload = { addEventListener: vi.fn() };
  onreadystatechange: (() => void) | null = null;
  private url = "";
  private headers: Record<string, string> = {};
  addEventListener() {}
  abort() {}
  open(_method: string, url: string) {
    this.url = url;
  }
  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }
  send(form: FormData) {
    const index = FakeXHR.sent.push({ url: this.url, form, headers: this.headers }) - 1;
    const { status, body } = FakeXHR.respond(index);
    this.readyState = 4;
    this.status = status;
    this.responseText = JSON.stringify(body);
    this.onreadystatechange?.();
  }
}

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  FakeXHR.sent = [];
  FakeXHR.respond = () => ({
    status: 200,
    body: { data: { name: "file-1", file_url: "/private/files/wrap.txt" } },
  });
  vi.stubGlobal("XMLHttpRequest", FakeXHR);
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
});
afterEach(() => vi.unstubAllGlobals());

describe("uploadFile", () => {
  it("posts a small file as one part to the File document route", async () => {
    const file = new File(["hello wrapper"], "wrap.txt");
    const { data } = await uploadFile(file, { is_private: true, folder: "Home/Attachments" });
    expect(data.file_url).toBe("/private/files/wrap.txt");
    expect(FakeXHR.sent).toHaveLength(1);
    const { url, form, headers } = FakeXHR.sent[0];
    expect(url).toBe("/api/v2/document/File");
    expect(headers.Accept).toBe("application/json");
    expect(headers["Content-Type"]).toBeUndefined();
    expect(form.get("total_chunk_count")).toBe("1");
    expect(form.get("chunk_index")).toBe("0");
    expect(form.get("is_private")).toBe("1");
    expect(form.get("folder")).toBe("Home/Attachments");
  });

  it("slices a large file by the chunk size and reads only the last answer", async () => {
    FakeXHR.respond = (index) =>
      index === 2
        ? { status: 200, body: { data: { name: "big", file_url: "/files/big.bin" } } }
        : { status: 200, body: {} };
    const file = new File(["0123456789"], "big.bin");
    const { data } = await uploadFile(file, {}, { chunkSize: 4 });
    expect(data.file_url).toBe("/files/big.bin");
    expect(FakeXHR.sent.map((s) => s.form.get("chunk_byte_offset"))).toEqual(["0", "4", "8"]);
    expect(FakeXHR.sent[0].form.get("total_chunk_count")).toBe("3");
    expect(FakeXHR.sent[0].form.get("total_file_size")).toBe("10");
  });

  it("refuses a last part that answers with no data, naming the route", async () => {
    FakeXHR.respond = () => ({ status: 200, body: {} });
    await expect(uploadFile(new File(["x"], "a.txt"), {})).rejects.toThrow(
      expect.objectContaining({
        type: "MissingData",
        message: "POST /document/File answered 200 with no data",
      })
    );
  });

  it("drops a field with no value rather than sending the word undefined", async () => {
    await uploadFile(new File(["x"], "pic.png"), { fieldname: undefined, optimize: 1 });
    expect(FakeXHR.sent[0].form.get("fieldname")).toBeNull();
    expect(FakeXHR.sent[0].form.get("optimize")).toBe("1");
  });

  it("reports the server's first error message on a failed part", async () => {
    FakeXHR.respond = () => ({
      status: 417,
      body: { errors: [{ type: "ValidationError", message: "File type not allowed" }] },
    });
    await expect(uploadFile(new File(["x"], "bad.exe"))).rejects.toThrow("File type not allowed");
  });

  it("names the size limit rather than the status when the server refuses the size", async () => {
    FakeXHR.respond = () => ({ status: 413, body: null });
    await expect(uploadFile(new File(["x"], "big.bin"))).rejects.toThrow(
      "File size exceeds the maximum allowed limit."
    );
  });
});

describe("attachFile", () => {
  it("posts to the record's attachments route and answers with the refreshed part", async () => {
    FakeXHR.respond = () => ({
      status: 200,
      body: {
        data: {
          file: "file-9",
          attachments: [{ name: "file-9", file_name: "a.txt", file_url: "/files/a.txt" }],
          users: { "alice@example.com": { full_name: "Alice" } },
        },
      },
    });
    const { data } = await attachFile("ToDo", "TODO/2026/1", new File(["x"], "a.txt"));
    expect(FakeXHR.sent[0].url).toBe("/api/v2/document/ToDo/TODO%2F2026%2F1/attachments");
    expect(data.file).toBe("file-9");
    expect(data.attachments[0].file_url).toBe("/files/a.txt");
    expect(data.users).toHaveProperty("alice@example.com");
  });
});

describe("removeAttachment", () => {
  it("deletes the file under the record's attachments route", async () => {
    fetchMock.mockImplementation(
      async () => new Response(JSON.stringify({ data: { attachments: [] } }), { status: 200 })
    );
    const { data } = await removeAttachment("ToDo", "TODO-1", "file-9");
    const [url, init] = fetchMock.mock.calls.at(-1)!;
    expect(String(url)).toBe("/api/v2/document/ToDo/TODO-1/attachments/file-9");
    expect(init?.method).toBe("DELETE");
    expect(data.attachments).toEqual([]);
  });
});

describe("an attachment write", () => {
  const row = { name: "file-9", file_name: "a.txt", file_url: "/files/a.txt" };
  const cachedAttachments = () => readCachedDocument("ToDo", "TODO-1")!.parts.attachments;

  beforeEach(() => {
    clearDataCache();
    const record = { data: { name: "TODO-1", modified: "2026-09-01 10:00:00" }, attachments: [] };
    feedRecordRead(takeTicket(), "ToDo", record, ["attachments"]);
  });

  it("feeds the refreshed part to the cache on attach and on remove", async () => {
    const attached = { data: { file: "file-9", attachments: [row] } };
    FakeXHR.respond = () => ({ status: 200, body: attached });
    await attachFile("ToDo", "TODO-1", new File(["x"], "a.txt"));
    expect(cachedAttachments()).toEqual([row]);
    const removed = JSON.stringify({ data: { attachments: [] } });
    fetchMock.mockImplementation(async () => new Response(removed));
    await removeAttachment("ToDo", "TODO-1", "file-9");
    expect(cachedAttachments()).toEqual([]);
  });
});

describe("downloadFile", () => {
  it("returns the bytes, with the headers every request sends", async () => {
    fetchMock.mockImplementation(async () => new Response("a,b\r\n", { status: 200 }));
    const blob = await downloadFile("/api/v2/method/some.export");
    expect(await blob.text()).toBe("a,b\r\n");
    const [url, init] = fetchMock.mock.calls.at(-1)!;
    expect(String(url)).toBe("/api/v2/method/some.export");
    expect((init?.headers as Record<string, string>).Accept).toBe("application/json");
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });

  it("throws the server's error when the download failed", async () => {
    fetchMock.mockImplementation(
      async () =>
        new Response(JSON.stringify({ errors: [{ type: "PermissionError", message: "Not allowed" }] }), {
          status: 403,
        })
    );
    await expect(downloadFile("/api/v2/method/some.export")).rejects.toThrow("Not allowed");
  });
});

// The upload primitive's own tests are under `ui/src/components`, which no runner picks up;
// its transport is the wrapper's caller, so its mapping is checked here.
describe("createFrappeTransport", () => {
  it("sends a detached file to the File route with the queue's args as fields", async () => {
    const { defaultTransport } = await import("../../components/FileUpload/useFileUpload");
    const result = await defaultTransport(
      new File(["x"], "pic.png"),
      { isPrivate: true, optimize: true, maxWidth: 800 },
      { signal: new AbortController().signal, onProgress: vi.fn() }
    );
    expect(result).toEqual({ file_url: "/private/files/wrap.txt", name: "file-1" });
    const { url, form } = FakeXHR.sent[0];
    expect(url).toBe("/api/v2/document/File");
    expect(form.get("folder")).toBe("Home/Attachments");
    expect(form.get("optimize")).toBe("1");
    expect(form.get("max_width")).toBe("800");
  });

  it("sends an attached file to the record's route and reads the row it made", async () => {
    FakeXHR.respond = () => ({
      status: 200,
      body: {
        data: {
          file: "file-9",
          attachments: [
            { name: "older", file_name: "a.txt", file_url: "/files/older.txt" },
            { name: "file-9", file_name: "a.txt", file_url: "/files/new.txt" },
          ],
        },
      },
    });
    const { defaultTransport } = await import("../../components/FileUpload/useFileUpload");
    const result = await defaultTransport(
      new File(["x"], "a.txt"),
      { attachTo: { doctype: "ToDo", docname: "TODO-1", fieldname: "image" } },
      { signal: new AbortController().signal, onProgress: vi.fn(), chunkSize: 4 }
    );
    expect(result).toEqual({ file_url: "/files/new.txt", name: "file-9" });
    expect(FakeXHR.sent[0].url).toBe("/api/v2/document/ToDo/TODO-1/attachments");
    expect(FakeXHR.sent[0].form.get("fieldname")).toBe("image");
  });
});
