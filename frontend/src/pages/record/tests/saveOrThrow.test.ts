import { describe, expect, it } from "vitest";
import { ActDeclined } from "@/acts/dispatcher";
import { cancelledError, saveOrThrow } from "../saveResponse";

const page = (saved: boolean, saveRefusal: unknown = null) => ({ save: async () => saved, saveRefusal }) as any;

describe("saveOrThrow", () => {
	it("resolves true when the record saved", async () => {
		expect(await saveOrThrow(page(true))).toBe(true);
	});

	it("throws the refusal the save gave, so the caller reads why", async () => {
		const refusal = new Error("Title is too long");
		await expect(saveOrThrow(page(false, refusal))).rejects.toBe(refusal);
	});

	it("says the page was left when the save gave no reason", async () => {
		await expect(saveOrThrow(page(false))).rejects.toThrow("The page was left before the record saved.");
	});

	it("ends declined when the reader closed the Required fields dialog", async () => {
		await expect(saveOrThrow(page(false, cancelledError()))).rejects.toBeInstanceOf(ActDeclined);
	});
});
