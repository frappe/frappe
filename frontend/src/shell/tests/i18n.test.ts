// Translations are fired, never awaited: a failure has to leave English on screen.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";

const fake = vi.hoisted(() => ({ getTranslations: vi.fn() }));

vi.mock("@framework/ui/api", () => ({ getTranslations: fake.getTranslations }));

import { __, __n, loadTranslations } from "@/i18n";

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
  fake.getTranslations.mockReset();
  for (const app of mounted.splice(0)) app.unmount();
});

async function load(data: Record<string, string> | undefined) {
  fake.getTranslations.mockResolvedValue({ data });
  await loadTranslations("v1", "fr");
}

function mountLabel(render: () => string) {
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp(defineComponent({ render: () => h("span", render()) }));
  app.mount(root);
  mounted.push(app);
  return root;
}

describe("loadTranslations", () => {
  it("translates from what the envelope carried", async () => {
    await load({ Save: "Enregistrer" });

    expect(fake.getTranslations).toHaveBeenCalledWith("fr", "v1");
    expect(__("Save")).toBe("Enregistrer");
  });

  it("keeps the messages it has when the answer carries no body", async () => {
    await load({ Close: "Fermer" });
    await load(undefined);

    expect(__("Close")).toBe("Fermer");
  });

  it("swallows a failure and leaves the text as it is", async () => {
    fake.getTranslations.mockRejectedValue(new Error("offline"));

    await expect(loadTranslations("v2", "de")).resolves.toBeUndefined();
    expect(__("Delete")).toBe("Delete");
  });

  it("re-renders a template that called __ before the fetch landed", async () => {
    let land: (value: { data: Record<string, string> }) => void = () => {};
    fake.getTranslations.mockReturnValue(
      new Promise((resolve) => (land = resolve)),
    );
    const pending = loadTranslations("v3", "fr");
    const root = mountLabel(() => __("Open"));
    expect(root.textContent).toBe("Open");

    land({ data: { Open: "Ouvrir" } });
    await pending;
    await nextTick();

    expect(root.textContent).toBe("Ouvrir");
  });
});

describe("__", () => {
  it("looks up text:context before text, and falls back to text", async () => {
    await load({ Open: "Ouvrir", "Open:Status": "Ouvert" });

    expect(__("Open", null, "Status")).toBe("Ouvert");
    expect(__("Open", null, "Colour")).toBe("Ouvrir");
    expect(__("Open")).toBe("Ouvrir");
  });

  it("fills {n} by position and keeps a placeholder with no value", async () => {
    await load({ "Deal {0} has {1} tasks": "L'affaire {0} a {1} tâches" });

    expect(__("Deal {0} has {1} tasks", ["CRM-DEAL-1", 3])).toBe(
      "L'affaire CRM-DEAL-1 a 3 tâches",
    );
    expect(__("Deal {0} has {1} tasks", ["CRM-DEAL-1"])).toBe(
      "L'affaire CRM-DEAL-1 a {1} tâches",
    );
  });

  it("returns an unknown key unchanged, replacements applied", async () => {
    await load({});

    expect(__("Nothing here {0}", ["yet"])).toBe("Nothing here yet");
  });
});

describe("__n", () => {
  it("picks the English form by count === 1, then translates it like __", async () => {
    await load({
      "{0} open task": "{0} tâche ouverte",
      "{0} open tasks": "{0} tâches ouvertes",
    });

    expect(__n("{0} open task", "{0} open tasks", 0, [0])).toBe(
      "0 tâches ouvertes",
    );
    expect(__n("{0} open task", "{0} open tasks", 1, [1])).toBe(
      "1 tâche ouverte",
    );
    expect(__n("{0} open task", "{0} open tasks", 2, [2])).toBe(
      "2 tâches ouvertes",
    );
  });

  it("honours a context on the chosen form", async () => {
    await load({ "{0} open task:Deal": "{0} affaire ouverte" });

    expect(__n("{0} open task", "{0} open tasks", 1, [1], "Deal")).toBe(
      "1 affaire ouverte",
    );
  });
});
