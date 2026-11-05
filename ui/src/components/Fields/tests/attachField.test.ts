import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h } from "vue";
import type { App } from "vue";
import AttachField from "../AttachField.vue";

/** An Attach Image value draws a thumbnail in the field, and a larger preview on hover. */

const IMAGE_URL = "/files/cover.png";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
	vi.useRealTimers();
	app?.unmount();
	host?.remove();
	app = undefined;
	host = undefined;
});

function render(fieldtype: string, modelValue: string | null) {
	host = document.createElement("div");
	document.body.appendChild(host);
	app = createApp({
		render: () =>
			h(AttachField, {
				field: { fieldname: "cover", fieldtype, label: "Cover" },
				modelValue,
			}),
	});
	app.mount(host);
	return host;
}

function imagesOf(root: ParentNode, url: string) {
	return [...root.querySelectorAll("img")].filter((img) => img.getAttribute("src") === url);
}

function hover(element: Element) {
	element.dispatchEvent(new PointerEvent("pointerenter", { pointerType: "mouse" }));
}

describe("AttachField for Attach Image", () => {
	it("draws a thumbnail of the image before the file name", () => {
		const root = render("Attach Image", IMAGE_URL);
		expect(imagesOf(root, IMAGE_URL)).toHaveLength(1);
		expect(root.querySelector("input")?.value).toBe("cover.png");
	});

	it("floats a larger preview when the thumbnail is hovered", async () => {
		const root = render("Attach Image", IMAGE_URL);
		const [thumbnail] = imagesOf(root, IMAGE_URL);
		vi.useFakeTimers();
		hover(thumbnail);
		await vi.advanceTimersByTimeAsync(400);
		const previews = imagesOf(document.body, IMAGE_URL).filter((img) => !root.contains(img));
		expect(previews).toHaveLength(1);
	});

	it("draws no thumbnail without a value", () => {
		const root = render("Attach Image", null);
		expect(root.querySelector("img")).toBeNull();
	});

	it("draws no thumbnail for a plain Attach field", () => {
		const root = render("Attach", IMAGE_URL);
		expect(root.querySelector("img")).toBeNull();
	});
});
