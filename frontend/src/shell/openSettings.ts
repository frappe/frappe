// The act that opens the settings dialog at a settings address. It writes the hash and never navigates.
import type { InjectionKey } from "vue";

/** Opens `#settings/<prefix>/<pane>/<block>`; each segment is optional, in order. */
export type OpenSettings = (prefix?: string, pane?: string, block?: string) => void;

/** The shell provides the act to everything it draws, the rail and the pages. */
export const OpenSettingsKey: InjectionKey<OpenSettings> = Symbol("OpenSettings");
