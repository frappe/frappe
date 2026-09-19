// Translations are fired, never awaited: a failure has to leave English on screen.
import { afterEach, describe, expect, it, vi } from "vitest";

const fake = vi.hoisted(() => ({ getTranslations: vi.fn() }));

vi.mock("@framework/ui/api", () => ({ getTranslations: fake.getTranslations }));

import { loadTranslations, translate } from "@/i18n";

afterEach(() => fake.getTranslations.mockReset());

describe("loadTranslations", () => {
  it("translates from what the envelope carried", async () => {
    fake.getTranslations.mockResolvedValue({ data: { Save: "Enregistrer" } });

    await loadTranslations("v1", "fr");

    expect(fake.getTranslations).toHaveBeenCalledWith("fr", "v1");
    expect(translate("Save")).toBe("Enregistrer");
  });

  it("keeps the messages it has when the answer carries no body", async () => {
    fake.getTranslations.mockResolvedValue({ data: { Close: "Fermer" } });
    await loadTranslations("v1", "fr");

    fake.getTranslations.mockResolvedValue({ data: undefined });
    await loadTranslations("v1", "fr");

    expect(translate("Close")).toBe("Fermer");
  });

  it("swallows a failure and leaves the text as it is", async () => {
    fake.getTranslations.mockRejectedValue(new Error("offline"));

    await expect(loadTranslations("v2", "de")).resolves.toBeUndefined();
    expect(translate("Delete")).toBe("Delete");
  });
});
