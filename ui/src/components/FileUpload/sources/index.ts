/**
 * Source registry — the extension seam for upload sources. Ships Device,
 * Camera, and Link; apps register their own (the deferred Library / Google
 * Drive sources, for example) with `registerUploadSource`. The dialog renders a
 * tab per source returned by `getUploadSources`.
 *
 * A source component receives no props beyond what its tab needs and emits
 * either `files` (a `File[]`) or `link` (a URL string); the dialog bridges those
 * into the uploader. Mirrors the registry shape of `fieldTypes.ts` so the
 * pattern is familiar.
 */
import type { Component } from "vue";
import DeviceSource from "./DeviceSource.vue";
import CameraSource from "./CameraSource.vue";
import LinkSource from "./LinkSource.vue";

export interface UploadSource {
  key: string;
  label: string;
  /** Lucide icon class (e.g. `lucide-monitor`). */
  icon: string;
  component: Component;
  /** Hidden when false at render time (e.g. camera with no media devices). */
  isAvailable?: () => boolean;
}

const sources: UploadSource[] = [
  {
    key: "device",
    label: "Device",
    icon: "lucide-monitor",
    component: DeviceSource,
  },
  {
    key: "camera",
    label: "Camera",
    icon: "lucide-camera",
    component: CameraSource,
    isAvailable: () =>
      typeof navigator !== "undefined" &&
      !!navigator.mediaDevices?.getUserMedia,
  },
  { key: "link", label: "Link", icon: "lucide-link", component: LinkSource },
];

/** Add or replace a source by key. */
export function registerUploadSource(source: UploadSource): void {
  const index = sources.findIndex((s) => s.key === source.key);
  if (index === -1) sources.push(source);
  else sources[index] = source;
}

/** Currently available sources, in registration order. */
export function getUploadSources(): UploadSource[] {
  return sources.filter((source) => source.isAvailable?.() ?? true);
}
