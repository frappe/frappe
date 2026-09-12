// The identity tile: what it lets the reader do, and how an upload reaches the draft.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

const { upload, Plain } = vi.hoisted(() => ({
	upload: vi.fn(async () => ({ file_url: "/files/new.png" })),
	Plain: (tag: string) =>
		defineComponent({
			inheritAttrs: false,
			setup: (_, { attrs, slots }) => () => h(tag, attrs, slots.default?.()),
		}),
}));

vi.mock("frappe-ui", () => ({
	Tooltip: Plain("span"),
	LoadingIndicator: Plain("i"),
	useFileUpload: () => ({ upload }),
}));

vi.mock("@/router/routeFor", () => ({ routeFor: () => ({ name: "record" }) }));

// The reader's access to the field's permlevel; the real one needs meta and roles from the server.
let fieldAccess = "write";
vi.mock("@framework/ui/composables/useDocPermissions", () => ({
	useDocPermissions: () => ({ fieldAccess: () => fieldAccess }),
}));

// The dialog stands in for itself: it exposes its transport and lets a test commit an upload.
const dialogs: any[] = [];
vi.mock("@framework/ui/components/FileUpload/FileUploadDialog.vue", () => ({
	// Vue unwraps an async import only when the module says it is one.
	__esModule: true,
	default: defineComponent({
		props: ["open", "transport"],
		emits: ["update:open", "committed", "uploading"],
		setup(props, { emit }) {
			dialogs.push({ props, emit });
			return () => h("dialog", { "data-upload": props.open });
		},
	}),
}));

import { CommitKey } from "@framework/ui/components/Fields/types";
import { PanelContextKey } from "../context";
import RecordImage from "../RecordImage.vue";

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
	dialogs.length = 0;
	upload.mockClear();
});

const META = { image_field: "image", fields: [{ fieldname: "image", fieldtype: "Attach Image" }] };

async function mount(doc: Record<string, any>, write = true, meta: any = META) {
	const docRef = ref(doc);
	const commit = { pending: vi.fn(), commit: vi.fn(), rowChanged: vi.fn() };
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(
		defineComponent({ render: () => h(RecordImage, { label: "Ann Example" }) })
	);
	app.provide(PanelContextKey, {
		doctype: "CRM Lead",
		docname: "LEAD-1",
		doc: docRef,
		meta: ref(meta),
		docinfo: ref({ permissions: { write: write ? 1 : 0 } }),
		controller: { page: { router: { resolve: () => ({ href: "/x" }) } } } as any,
		run: () => {},
		reloadDocinfo: async () => {},
	});
	app.provide(CommitKey, commit);
	app.mount(root);
	mounted.push(app);
	await nextTick();
	return { root, docRef, commit };
}

const button = (root: HTMLElement, label: string) =>
	root.querySelector<HTMLElement>(`button[aria-label="${label}"]`);

describe("the identity tile", () => {
	it("shows the initials until a picture exists, and a camera with write", async () => {
		const { root } = await mount({});
		expect(root.querySelector("img")).toBeNull();
		expect(root.textContent?.trim()).toBe("AE");
		expect(button(root, "Add image")).not.toBeNull();
	});

	it("offers nothing on a field whose permlevel the reader cannot write", async () => {
		fieldAccess = "read";
		try {
			const { root } = await mount({});
			expect(button(root, "Add image")).toBeNull();
		} finally {
			fieldAccess = "write";
		}
	});

	it("offers nothing without write, even on a plain field", async () => {
		const { root } = await mount({ image: "/files/ann.png" }, false);
		expect(root.querySelector("img")?.getAttribute("src")).toBe("/files/ann.png");
		expect(button(root, "Replace image")).toBeNull();
		expect(button(root, "Remove image")).toBeNull();
	});

	it("falls back to the initials when the picture fails to load", async () => {
		const { root } = await mount({ image: "/files/gone.png" });
		root.querySelector("img")!.dispatchEvent(new Event("error"));
		await nextTick();
		expect(root.querySelector("img")).toBeNull();
		expect(root.textContent?.trim()).toBe("AE");
	});

	it("lands an upload in the draft through the commit channel, attached to the record", async () => {
		const { root, docRef, commit } = await mount({});
		button(root, "Add image")!.click();
		// The dialog is an async component, so its mount lands a tick or two later.
		await vi.waitFor(() => expect(dialogs.length).toBe(1));
		const dialog = dialogs[0];
		expect(dialog.props.open).toBe(true);

		await dialog.props.transport(new File([""], "dot.png"), { isPrivate: true }, {
			signal: new AbortController().signal,
			onProgress: () => {},
		});
		expect(upload.mock.calls[0][1]).toMatchObject({
			doctype: "CRM Lead",
			docname: "LEAD-1",
			fieldname: "image",
			private: true,
		});

		dialog.emit("committed", [{ file_url: "/files/new.png", file_name: "new.png", is_private: true }]);
		await nextTick();
		expect(docRef.value.image).toBe("/files/new.png");
		expect(commit.commit).toHaveBeenCalledWith("image", "/files/new.png");
		expect(root.querySelector("dialog")).toBeNull();
	});

	it("removes the picture through the same channel", async () => {
		const { root, docRef, commit } = await mount({ image: "/files/ann.png" });
		button(root, "Remove image")!.click();
		await nextTick();
		expect(docRef.value.image).toBe("");
		expect(commit.commit).toHaveBeenCalledWith("image", "");
	});

	it("links a fetched picture to its source instead of editing it", async () => {
		const meta = {
			image_field: "image",
			fields: [
				{ fieldname: "image", fetch_from: "contact.image" },
				{ fieldname: "contact", fieldtype: "Link", options: "Contact", label: "Contact" },
			],
		};
		const { root } = await mount({ image: "/files/c.png", contact: "CONT-1" }, true, meta);
		expect(button(root, "Replace image")).toBeNull();
		expect(root.querySelector("a")?.getAttribute("href")).toBe("/x");
	});
});
