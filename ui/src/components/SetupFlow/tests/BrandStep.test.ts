import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import type { App } from "vue";

const upload = vi.hoisted(() => vi.fn());
vi.mock("frappe-ui", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  useFileUpload: () => ({ upload, isUploading: { value: false } }),
}));

let app: App | null = null;

async function mountStep(save: () => Promise<unknown>) {
  const { default: BrandStep } = await import("../BrandStep.vue");
  const done = vi.fn();
  const el = document.createElement("div");
  document.body.appendChild(el);
  app = createApp({ render: () => h(BrandStep, { save, onDone: done }) });
  app.mount(el);
  return { el, done };
}

async function typeName(el: HTMLElement, value: string) {
  const input = el.querySelector('input:not([type="file"])') as HTMLInputElement;
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await nextTick();
}

const submit = async (el: HTMLElement) => {
  el.querySelector("form")!.dispatchEvent(new Event("submit"));
  await new Promise((resolve) => setTimeout(resolve, 0));
  await nextTick();
};

afterEach(() => {
  app?.unmount();
  app = null;
  upload.mockReset();
});

describe("BrandStep", () => {
  it("saves the name through the app and moves on", async () => {
    const save = vi.fn(async () => null);
    const { el, done } = await mountStep(save);
    const button = el.querySelector('button[type="submit"]') as HTMLButtonElement;
    expect(button.disabled).toBe(true);

    await typeName(el, "  Acme Inc ");
    expect(el.textContent).toContain("A");
    expect(button.disabled).toBe(false);
    await submit(el);
    expect(save).toHaveBeenCalledWith({ name: "Acme Inc", logo: "" });
    expect(done).toHaveBeenCalledTimes(1);
  });

  it("stays and says why when the app cannot save", async () => {
    const save = vi.fn(async () => Promise.reject({ messages: ["Name is too long"] }));
    const { el, done } = await mountStep(save);
    await typeName(el, "Acme");
    await submit(el);
    expect(done).not.toHaveBeenCalled();
    expect(el.textContent).toContain("Name is too long");
  });

  it("uploads a chosen image as the logo, and refuses anything else", async () => {
    upload.mockResolvedValue({ file_url: "/files/acme.png" });
    const { el } = await mountStep(async () => null);
    const picker = el.querySelector('input[type="file"]') as HTMLInputElement;

    const choose = async (file: File) => {
      Object.defineProperty(picker, "files", { value: [file], configurable: true });
      picker.dispatchEvent(new Event("change"));
      await nextTick();
      await nextTick();
    };

    await choose(new File(["x"], "notes.txt", { type: "text/plain" }));
    expect(upload).not.toHaveBeenCalled();
    expect(el.textContent).toContain("Choose an image file.");

    await choose(new File(["x"], "acme.png", { type: "image/png" }));
    expect(upload).toHaveBeenCalledTimes(1);
    expect(el.querySelector("img")?.getAttribute("src")).toBe("/files/acme.png");
    expect(el.textContent).toContain("Reupload");
    expect(el.textContent).toContain("Remove");
  });
});
