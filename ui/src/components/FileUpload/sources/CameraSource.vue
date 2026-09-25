<template>
	<div class="flex flex-col items-center gap-3">
		<div
			v-if="error"
			class="flex min-h-64 w-full items-center justify-center rounded-lg border border-dashed border-outline-gray-2 p-6 text-center text-p-sm text-ink-gray-6"
		>
			{{ error }}
		</div>
		<template v-else>
			<video
				v-show="!snapshot"
				ref="video"
				class="max-h-80 w-full rounded-lg bg-surface-gray-10"
				autoplay
				playsinline
			/>
			<canvas v-show="snapshot" ref="canvas" class="max-h-80 w-full rounded-lg" />
			<div class="flex w-full items-center justify-end gap-2">
				<template v-if="!snapshot">
					<Button
						variant="subtle"
						icon-left="lucide-switch-camera"
						label="Switch camera"
						aria-label="Switch camera"
						@click="switchCamera"
					/>
					<Button
						icon-left="lucide-camera"
						label="Capture"
						aria-label="Capture"
						@click="capture"
					/>
				</template>
				<template v-else>
					<Button variant="subtle" label="Retake" aria-label="Retake" @click="retake" />
					<Button
						variant="solid"
						label="Use photo"
						aria-label="Use photo"
						@click="usePhoto"
					/>
				</template>
			</div>
		</template>
	</div>
</template>

<script setup lang="ts">
// Camera source: opens the device camera with getUserMedia, previews the live
// feed, and turns a captured frame into a PNG `File` emitted via `files`. The
// MediaStream is always torn down — on unmount and whenever the camera view is
// torn down — so the camera light never lingers. Gated on
// `navigator.mediaDevices`; absence surfaces as an inline message.
import { onBeforeUnmount, onMounted, ref } from "vue";
import { Button } from "frappe-ui";

const emit = defineEmits<{ files: [File[]] }>();

const video = ref<HTMLVideoElement | null>(null);
const canvas = ref<HTMLCanvasElement | null>(null);
const snapshot = ref<string | null>(null);
const error = ref<string | null>(null);
const facingMode = ref<"environment" | "user">("environment");

let stream: MediaStream | null = null;

onMounted(start);
onBeforeUnmount(stop);

async function start() {
	if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
		error.value = "No camera is available on this device.";
		return;
	}
	try {
		stream = await navigator.mediaDevices.getUserMedia({
			video: { facingMode: facingMode.value },
			audio: false,
		});
		error.value = null;
		if (video.value) video.value.srcObject = stream;
	} catch {
		error.value = "Could not access the camera. Check permissions and try again.";
	}
}

function stop() {
	stream?.getTracks().forEach((track) => track.stop());
	stream = null;
}

function capture() {
	const v = video.value;
	const c = canvas.value;
	if (!v || !c) return;
	c.width = v.videoWidth;
	c.height = v.videoHeight;
	c.getContext("2d")?.drawImage(v, 0, 0, c.width, c.height);
	snapshot.value = c.toDataURL("image/png");
}

function retake() {
	snapshot.value = null;
}

function usePhoto() {
	const c = canvas.value;
	if (!c) return;
	// JPEG, not PNG: a full-resolution camera frame as PNG is several MB and can
	// trip max_file_size restrictions; JPEG at 0.92 is a fraction of the size with
	// no visible loss for a photo.
	c.toBlob(
		(blob) => {
			if (!blob) return;
			const name = `capture-${captureSeq()}.jpg`;
			emit("files", [new File([blob], name, { type: "image/jpeg" })]);
			snapshot.value = null;
		},
		"image/jpeg",
		0.92
	);
}

async function switchCamera() {
	const previous = facingMode.value;
	facingMode.value = previous === "environment" ? "user" : "environment";
	stop();
	await start();
	// A device with only one camera (or one that rejects the requested facing
	// mode) leaves us with no stream — fall back to the camera that was working
	// rather than stranding the user on a blank preview.
	if (!stream) {
		facingMode.value = previous;
		await start();
	}
}
</script>

<script lang="ts">
// Process-wide counter for unique capture filenames (avoids Math.random()).
let seq = 0;
function captureSeq() {
	return ++seq;
}
</script>
