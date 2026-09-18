import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defaultTransport } from "../useFileUpload";

class FakeXHR {
  static sent: { url: string; form: FormData; headers: Record<string, string> }[] = [];
  static respond: (index: number) => { status: number; body: unknown } = () => ({
    status: 200,
    body: { data: { file_url: "/private/files/wrap.txt" } },
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

const ctx = () => ({ signal: new AbortController().signal, onProgress: vi.fn() });

beforeEach(() => {
  FakeXHR.sent = [];
  vi.stubGlobal("XMLHttpRequest", FakeXHR);
});
afterEach(() => vi.unstubAllGlobals());

describe("defaultTransport", () => {
  it("posts a small file as one chunk to the v2 route and reads data.file_url", async () => {
    const file = new File(["hello wrapper"], "wrap.txt");
    const result = await defaultTransport(file, { isPrivate: true }, ctx());
    expect(result).toEqual({ file_url: "/private/files/wrap.txt" });
    expect(FakeXHR.sent).toHaveLength(1);
    const { url, form, headers } = FakeXHR.sent[0];
    expect(url).toBe("/api/v2/method/upload_file");
    expect(headers.Accept).toBe("application/json");
    expect(headers["Content-Type"]).toBeUndefined();
    expect(form.get("total_chunk_count")).toBe("1");
    expect(form.get("chunk_index")).toBe("0");
    expect(form.get("is_private")).toBe("1");
  });

  it("slices a large file by the boot chunk size and reads only the last response", async () => {
    (globalThis as any).frappe = { boot: { file_chunk_size: 4 } };
    FakeXHR.respond = (index) =>
      index === 2
        ? { status: 200, body: { data: { file_url: "/files/big.bin" } } }
        : { status: 200, body: { data: null } };
    const file = new File(["0123456789"], "big.bin");
    const result = await defaultTransport(file, {}, ctx());
    delete (globalThis as any).frappe;
    expect(result).toEqual({ file_url: "/files/big.bin" });
    expect(FakeXHR.sent.map((s) => s.form.get("chunk_byte_offset"))).toEqual(["0", "4", "8"]);
    expect(FakeXHR.sent[0].form.get("total_chunk_count")).toBe("3");
  });

  it("names the record and field the file attaches to, and nothing when unattached", async () => {
    FakeXHR.respond = () => ({ status: 200, body: { data: { file_url: "/files/pic.png" } } });
    const file = new File(["x"], "pic.png");
    await defaultTransport(file, {}, ctx());
    expect(FakeXHR.sent[0].form.get("doctype")).toBeNull();
    await defaultTransport(
      file,
      { attachTo: { doctype: "CRM Lead", docname: "LEAD-1", fieldname: "image" } },
      ctx()
    );
    const { form } = FakeXHR.sent[1];
    expect(form.get("doctype")).toBe("CRM Lead");
    expect(form.get("docname")).toBe("LEAD-1");
    expect(form.get("fieldname")).toBe("image");
  });

  it("reports the server's first error message on a failed chunk", async () => {
    FakeXHR.respond = () => ({
      status: 417,
      body: { errors: [{ type: "ValidationError", message: "File type not allowed" }] },
    });
    const file = new File(["x"], "bad.exe");
    await expect(defaultTransport(file, {}, ctx())).rejects.toThrow("File type not allowed");
  });
});
