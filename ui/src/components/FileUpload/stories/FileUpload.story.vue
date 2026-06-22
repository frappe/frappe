<template>
	<div class="p-6 max-w-3xl">
		<!-- ── Standalone upload-primitive playground ──────────────────────────
		     The Attach/Attach Image/Image fields in the hand-written schema are
		     driven by the same primitive; here we exercise the consumers directly
		     with a fake transport (placeholder URL + simulated progress). -->
		<h3 class="mb-3 text-lg-semibold text-ink-gray-9">Upload primitive — standalone</h3>

		<div class="flex flex-col gap-6">
			<div>
				<div class="mb-2 text-sm-medium text-ink-gray-7">
					Multi-file dialog (inline progress)
				</div>
				<Button label="Open inline dialog" @click="inlineOpen = true" />
				<FileUploadDialog
					v-if="inlineOpen"
					v-model:open="inlineOpen"
					title="Upload (inline)"
					:multiple="true"
					:transport="fakeTransport"
					progressMode="inline"
					@committed="onStandaloneCommit"
				/>
			</div>

			<div>
				<div class="mb-2 text-sm-medium text-ink-gray-7">
					Multi-file dialog (tray — survives close)
				</div>
				<Button label="Open tray dialog" @click="trayOpen = true" />
				<FileUploadDialog
					v-if="trayOpen"
					v-model:open="trayOpen"
					title="Upload (tray)"
					:multiple="true"
					:transport="fakeTransport"
					progressMode="tray"
					@committed="onStandaloneCommit"
				/>
			</div>

			<div>
				<div class="mb-2 text-sm-medium text-ink-gray-7">
					Image dialog with crop + compress
				</div>
				<Button label="Open image dialog" @click="cropOpen = true" />
				<FileUploadDialog
					v-if="cropOpen"
					v-model:open="cropOpen"
					title="Upload image"
					:multiple="true"
					:imageOnly="true"
					:crop="true"
					:transport="fakeTransport"
					@committed="onStandaloneCommit"
				/>
			</div>

			<div>
				<div class="mb-2 text-sm-medium text-ink-gray-7">
					Attachments list (array of results)
				</div>
				<AttachmentsList v-model="gallery" :transport="fakeTransport" />
			</div>

			<pre class="text-xs text-ink-gray-6">committed = {{ lastCommitted }}</pre>
		</div>

		<!-- App-root singleton; here mounted in the story root. `side` picks the
		     bottom corner — toggle to see where the tray pins. -->
		<div class="mt-8 flex items-center gap-2 text-sm text-ink-gray-7">
			<span>side</span>
			<Select v-model="traySide" :options="['right', 'left']" />
		</div>
		<UploadTray :side="traySide" />
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Button, Select } from "frappe-ui";
import FileUploadDialog from "../FileUploadDialog.vue";
import AttachmentsList from "../AttachmentsList.vue";
import UploadTray from "../UploadTray.vue";
import type { UploadResult, UploadTransport } from "../types";

// Fake transport for the stories: no backend, just a placeholder URL and a
// simulated progress ramp (honoring the abort signal). The standalone consumers
// receive it via their `:transport` prop.
const fakeTransport: UploadTransport = (file, _args, ctx) =>
	new Promise((resolve, reject) => {
		const total = file.size || 1000;
		let loaded = 0;
		const onAbort = () => reject(new DOMException("Cancelled", "AbortError"));
		ctx.signal.addEventListener("abort", onAbort, { once: true });
		const tick = () => {
			if (ctx.signal.aborted) return;
			loaded = Math.min(total, loaded + Math.ceil(total / 4));
			ctx.onProgress(loaded, total);
			if (loaded < total) {
				setTimeout(tick, 250);
			} else {
				ctx.signal.removeEventListener("abort", onAbort);
				resolve({
					file_url: `https://placehold.co/600x400?text=${encodeURIComponent(file.name)}`,
				});
			}
		};
		setTimeout(tick, 250);
	});

// Standalone playground state.
const inlineOpen = ref(false);
const trayOpen = ref(false);
const cropOpen = ref(false);
const gallery = ref<UploadResult[]>([]);
const lastCommitted = ref<UploadResult[]>([]);

// Tray placement control (default right, matching the component default).
const traySide = ref<"left" | "right">("right");

function onStandaloneCommit(results: UploadResult[]) {
	lastCommitted.value = results;
}
</script>
