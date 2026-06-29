import { describe, expect, it, vi } from "vitest";
import { useUploader } from "../useUploader";
import type { UploadTransport } from "../types";

/** A fake transport that resolves with a deterministic url and reports progress. */
function fakeTransport(): UploadTransport {
  return async (file, _args, ctx) => {
    ctx.onProgress(file.size / 2, file.size);
    ctx.onProgress(file.size, file.size);
    return { file_url: `/files/${file.name}` };
  };
}

function makeFile(name: string, size = 100, type = "text/plain"): File {
  const blob = new Blob([new Uint8Array(size)], { type });
  return new File([blob], name, { type });
}

describe("useUploader", () => {
  it("adds files and commits them via the transport", async () => {
    const uploader = useUploader({
      transport: fakeTransport(),
      multiple: true,
    });
    uploader.add([makeFile("a.txt"), makeFile("b.txt")]);
    expect(uploader.items.length).toBe(2);

    const results = await uploader.commit();
    expect(results).toEqual([
      { file_url: "/files/a.txt", file_name: "a.txt", is_private: true },
      { file_url: "/files/b.txt", file_name: "b.txt", is_private: true },
    ]);
    expect(uploader.items.every((i) => i.status === "done")).toBe(true);
    expect(uploader.progress.value).toBe(1);
  });

  it("enforces single-file mode (multiple: false)", () => {
    const uploader = useUploader({
      transport: fakeTransport(),
      multiple: false,
    });
    uploader.add([makeFile("a.txt")]);
    uploader.add([makeFile("b.txt")]);
    expect(uploader.items.length).toBe(1);
    expect(uploader.errors.value.length).toBeGreaterThan(0);
  });

  it("rejects files over max_file_size with a friendly message", () => {
    const uploader = useUploader({
      transport: fakeTransport(),
      multiple: true,
      restrictions: { max_file_size: 50 },
    });
    uploader.add([makeFile("big.txt", 100)]);
    expect(uploader.items.length).toBe(0);
    expect(uploader.errors.value[0]).toMatch(/exceeds/);
  });

  it("rejects disallowed file types (imageOnly)", () => {
    const uploader = useUploader({
      transport: fakeTransport(),
      multiple: true,
      imageOnly: true,
    });
    uploader.add([makeFile("doc.txt", 10, "text/plain")]);
    uploader.add([makeFile("pic.png", 10, "image/png")]);
    expect(uploader.items.map((i) => i.name)).toEqual(["pic.png"]);
  });

  it("honors allowed_file_types extensions", () => {
    const uploader = useUploader({
      transport: fakeTransport(),
      multiple: true,
      restrictions: { allowed_file_types: [".pdf"] },
    });
    uploader.add([makeFile("a.txt"), makeFile("b.pdf", 10, "application/pdf")]);
    expect(uploader.items.map((i) => i.name)).toEqual(["b.pdf"]);
  });

  it("caps the queue at max_number_of_files", () => {
    const uploader = useUploader({
      transport: fakeTransport(),
      multiple: true,
      restrictions: { max_number_of_files: 2 },
    });
    uploader.add([makeFile("a.txt"), makeFile("b.txt"), makeFile("c.txt")]);
    expect(uploader.items.length).toBe(2);
    expect(uploader.canAddMore.value).toBe(false);
  });

  it("detects duplicates by name + size", () => {
    const uploader = useUploader({
      transport: fakeTransport(),
      multiple: true,
    });
    uploader.add([makeFile("a.txt", 100)]);
    uploader.add([makeFile("a.txt", 100)]);
    expect(uploader.items.length).toBe(1);
    expect(uploader.errors.value[0]).toMatch(/already in the list/);
  });

  it("reorders queue items", () => {
    const uploader = useUploader({
      transport: fakeTransport(),
      multiple: true,
    });
    uploader.add([makeFile("a.txt"), makeFile("b.txt"), makeFile("c.txt")]);
    uploader.reorder(0, 2);
    expect(uploader.items.map((i) => i.name)).toEqual([
      "b.txt",
      "c.txt",
      "a.txt",
    ]);
  });

  it("removes an item", () => {
    const uploader = useUploader({
      transport: fakeTransport(),
      multiple: true,
    });
    uploader.add([makeFile("a.txt"), makeFile("b.txt")]);
    uploader.remove(uploader.items[0].id);
    expect(uploader.items.map((i) => i.name)).toEqual(["b.txt"]);
  });

  it("commits a web link directly without calling the transport", async () => {
    const transport = vi.fn(fakeTransport());
    const uploader = useUploader({ transport, multiple: true });
    uploader.addLink("https://example.com/path/photo.png");
    const results = await uploader.commit();
    expect(transport).not.toHaveBeenCalled();
    expect(results[0]).toEqual({
      file_url: "https://example.com/path/photo.png",
      file_name: "photo.png",
      is_private: true,
    });
  });

  it("marks an item errored when the transport throws, then retries", async () => {
    let attempts = 0;
    const transport: UploadTransport = async (file, _a, _c) => {
      attempts++;
      if (attempts === 1) throw new Error("boom");
      return { file_url: `/files/${file.name}` };
    };
    const uploader = useUploader({ transport, multiple: true });
    uploader.add([makeFile("a.txt")]);

    await uploader.commit();
    expect(uploader.items[0].status).toBe("error");
    expect(uploader.items[0].error).toBe("boom");

    uploader.retry(uploader.items[0].id);
    expect(uploader.items[0].status).toBe("idle");
    const results = await uploader.commit();
    expect(results[0].file_url).toBe("/files/a.txt");
  });

  it("returns only the delta on re-commit after a partial failure", async () => {
    // a.txt succeeds; b.txt fails the first attempt, then succeeds on retry.
    const transport: UploadTransport = async (file) => {
      if (
        file.name === "b.txt" &&
        !/done/.test((transport as any)._seen ?? "")
      ) {
        (transport as any)._seen = "done";
        throw new Error("boom");
      }
      return { file_url: `/files/${file.name}` };
    };
    const uploader = useUploader({ transport, multiple: true });
    uploader.add([makeFile("a.txt"), makeFile("b.txt")]);

    const first = await uploader.commit();
    expect(first.map((r) => r.file_url)).toEqual(["/files/a.txt"]);
    expect(uploader.items[1].status).toBe("error");

    uploader.retry(uploader.items[1].id);
    const second = await uploader.commit();
    // Only b.txt — a.txt was already committed and must NOT be re-emitted.
    expect(second.map((r) => r.file_url)).toEqual(["/files/b.txt"]);
  });

  it("scopes commit to the given ids (per-item retry)", async () => {
    // Both rows fail the first pass, then succeed once retried.
    const failed = new Set<string>();
    const transport: UploadTransport = async (file) => {
      if (!failed.has(file.name)) {
        failed.add(file.name);
        throw new Error("boom");
      }
      return { file_url: `/files/${file.name}` };
    };
    const uploader = useUploader({ transport, multiple: true });
    uploader.add([makeFile("a.txt"), makeFile("b.txt")]);

    await uploader.commit();
    expect(uploader.items.map((i) => i.status)).toEqual(["error", "error"]);

    // Retry only the first row: the scoped commit re-uploads a.txt and leaves
    // b.txt untouched (still errored), and returns only a.txt's result.
    const aId = uploader.items[0].id;
    uploader.retry(aId);
    const delta = await uploader.commit([aId]);
    expect(delta.map((r) => r.file_url)).toEqual(["/files/a.txt"]);
    expect(uploader.items.map((i) => i.status)).toEqual(["done", "error"]);
  });

  it("rejects a duplicate web link", () => {
    const uploader = useUploader({
      transport: fakeTransport(),
      multiple: true,
    });
    expect(uploader.addLink("https://example.com/a.pdf")).not.toBeNull();
    expect(uploader.addLink("https://example.com/a.pdf")).toBeNull();
    expect(uploader.items.length).toBe(1);
    expect(
      uploader.errors.value.some((e) => /already in the list/.test(e))
    ).toBe(true);
  });

  it("applies the global private toggle to queued items", () => {
    const uploader = useUploader({
      transport: fakeTransport(),
      multiple: true,
    });
    uploader.add([makeFile("a.txt")]);
    uploader.setAllPrivate(false);
    expect(uploader.items[0].isPrivate).toBe(false);
  });

  it("rejects javascript:/data: links but accepts http(s) and site-relative", () => {
    const transport = vi.fn(fakeTransport());
    const uploader = useUploader({ transport, multiple: true });

    expect(uploader.addLink("javascript:alert(1)")).toBeNull();
    expect(uploader.addLink("data:text/html,<script>1</script>")).toBeNull();
    expect(uploader.items.length).toBe(0);
    expect(uploader.errors.value.some((e) => /http/i.test(e))).toBe(true);

    expect(uploader.addLink("https://example.com/a.pdf")).not.toBeNull();
    expect(uploader.addLink("/files/b.pdf")).not.toBeNull();
    expect(uploader.items.map((i) => i.name)).toEqual(["a.pdf", "b.pdf"]);
  });

  it("passes typeless files under a MIME-only rule but not an extension rule", () => {
    // Empty file.type can't match a MIME glob; image-only should still accept it.
    const img = useUploader({
      transport: fakeTransport(),
      multiple: true,
      imageOnly: true,
    });
    img.add([makeFile("photo", 10, "")]);
    expect(img.items.length).toBe(1);

    // An extension restriction stays authoritative — a typeless file is rejected.
    const ext = useUploader({
      transport: fakeTransport(),
      multiple: true,
      restrictions: { allowed_file_types: [".pdf"] },
    });
    ext.add([makeFile("mystery", 10, "")]);
    expect(ext.items.length).toBe(0);
  });

  it("ignores a re-entrant commit while one is already in flight", async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    const transport: UploadTransport = async (file) => {
      await gate;
      return { file_url: `/files/${file.name}` };
    };
    const uploader = useUploader({ transport, multiple: true });
    uploader.add([makeFile("a.txt")]);

    const first = uploader.commit();
    // The first pass set the item to "uploading" before awaiting the gate, so a
    // second commit must bail out rather than double-upload.
    const second = await uploader.commit();
    expect(second).toEqual([]);

    release();
    const results = await first;
    expect(results.map((r) => r.file_url)).toEqual(["/files/a.txt"]);
    expect(uploader.items[0].status).toBe("done");
  });

  it("replaces a file (crop result) and resets its status", () => {
    const uploader = useUploader({
      transport: fakeTransport(),
      multiple: true,
    });
    uploader.add([makeFile("a.png", 100, "image/png")]);
    const id = uploader.items[0].id;
    uploader.replaceFile(id, makeFile("a-cropped.png", 60, "image/png"));
    expect(uploader.items[0].name).toBe("a-cropped.png");
    expect(uploader.items[0].size).toBe(60);
    expect(uploader.items[0].status).toBe("idle");
  });
});
