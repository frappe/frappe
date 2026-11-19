import { afterEach, describe, expect, it } from "vitest";
import { createApp, defineComponent, h, inject } from "vue";
import { UploadTransportKey } from "@framework/ui/FileUpload";
import { CreateRecordKey } from "@framework/ui/fields/types";
import { CommitKey, NO_COMMIT } from "@framework/ui/FormLayout/types";
import { refuseWrites } from "../previewRefusals";

const apps: ReturnType<typeof createApp>[] = [];
afterEach(() => apps.splice(0).forEach((app) => app.unmount()));

function previewInjections() {
	const seen: Record<string, unknown> = {};
	const Field = defineComponent(() => {
		seen.commit = inject(CommitKey);
		seen.upload = inject(UploadTransportKey);
		seen.create = inject(CreateRecordKey, undefined);
		return () => null;
	});
	const Preview = defineComponent(() => {
		refuseWrites();
		return () => h(Field);
	});
	const app = createApp(Preview);
	app.provide(CreateRecordKey, { open: async () => ({}), useRight: () => ({ value: true }) as never });
	apps.push(app);
	app.mount(document.createElement("div"));
	return seen;
}

describe("Preview's refusals", () => {
	it("drop field events", () => {
		expect(previewInjections().commit).toBe(NO_COMMIT);
	});

	it("refuse uploads", async () => {
		const upload = previewInjections().upload as (...args: never[]) => Promise<unknown>;
		await expect(upload()).rejects.toThrow("Preview does not upload files.");
	});

	it("hide the app's Create from Link fields", () => {
		expect(previewInjections().create).toBeNull();
	});
});
