/**
 * Source registry — the list of "add" entries the dialog's add-menu renders.
 * Ships Device, Camera, and Link; apps register their own with
 * `registerUploadSource`. Each entry contributes a row (icon + label) to the
 * menu, gated by `isAvailable` (e.g. camera with no media devices).
 *
 * The dialog owns how each source is collected — a native picker for Device, an
 * inline composer for Link, and `CameraSource` for Camera — keyed off `key`, so
 * the registry carries presentation metadata only, not a renderable component.
 * Mirrors the registry shape of `fieldTypes.ts` so the pattern is familiar.
 */
export interface UploadSource {
  key: string;
  label: string;
  /** Lucide icon class (e.g. `lucide-monitor`). */
  icon: string;
  /** Hidden when false at render time (e.g. camera with no media devices). */
  isAvailable?: () => boolean;
}

const sources: UploadSource[] = [
  { key: "device", label: "Device", icon: "lucide-monitor" },
  {
    key: "camera",
    label: "Camera",
    icon: "lucide-camera",
    isAvailable: () =>
      typeof navigator !== "undefined" &&
      !!navigator.mediaDevices?.getUserMedia,
  },
  { key: "link", label: "Link", icon: "lucide-link" },
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
