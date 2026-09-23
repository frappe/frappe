// `page.composer`: the writers the band at the foot of a composer tab offers, and the
// acts that open and close one. The host draws the band and keeps the drafts.
import { Surface } from "./surface";
import { WRITER_ITEM_KEYS } from "./types";
import type {
  ComposerOpenOptions,
  ComposerWindow,
  PageComposer,
  TabItem,
  WriterItem,
} from "./types";

const WINDOWS: readonly ComposerWindow[] = ["docked", "floating"];

/** The built-in tabs that draw the band; a script's tab joins them with `composer: true`. */
export const COMPOSER_TABS = ["activity", "emails"];

export function isComposerTab(item: TabItem): boolean {
  return COMPOSER_TABS.includes(item.name) || Boolean(item.composer);
}

/** Where `open` lands: the reader's tab if it draws the band, else `activity`, else the first. */
export function composerTab(tabs: TabItem[], active: string): string | undefined {
  const drawing = tabs.filter(isComposerTab);
  const landing =
    drawing.find((tab) => tab.name === active) ??
    drawing.find((tab) => tab.name === "activity") ??
    drawing[0];
  return landing?.name;
}

export interface ComposerHost {
  openWriter(name: string, options: ComposerOpenOptions): void;
  closeWriter(): void;
  activeWriter(): string;
  /** The open card's place while this record's writer is open, else the reader's own choice. */
  windowState(): ComposerWindow;
  /** Moves the open card of this record's writer; the reader's own choice stays. */
  setWindow(window: ComposerWindow): void;
}

export class ComposerSurface extends Surface<WriterItem> implements PageComposer {
  private heldOpen: { name: string; options: ComposerOpenOptions } | null = null;

  constructor(private readonly host: ComposerHost) {
    super({ surface: "composer", keys: WRITER_ITEM_KEYS });
  }

  get active() {
    return this.host.activeWriter();
  }

  get window(): ComposerWindow {
    return this.host.windowState();
  }

  set window(value: ComposerWindow) {
    if (!WINDOWS.includes(value)) this.refuseWindow(value, 'it takes "docked" or "floating"');
    else if (!this.active) this.refuseWindow(value, "no writer of this record is open");
    else this.host.setWindow(value);
  }

  /** Called in a replay, the open waits for `releaseOpen`, as `activity.scrollTo` waits. */
  open(name: string, options: ComposerOpenOptions = {}) {
    if (!this.canOpen(name)) return;
    if (this.replaying) this.heldOpen = { name, options };
    else this.deliver(name, options);
  }

  close() {
    this.heldOpen = null;
    this.host.closeWriter();
  }

  // Host side, below: not part of what a script may call.

  releaseOpen() {
    const held = this.heldOpen;
    this.heldOpen = null;
    if (held && this.canOpen(held.name, "it left the composer before the replay settled"))
      this.deliver(held.name, held.options);
  }

  private canOpen(name: string, gone = "no such writer") {
    if (!this.has(name)) return this.refuse(name, gone);
    if (!this.isVisible(name)) return this.refuse(name, "it is hidden — show() reveals a writer");
    return true;
  }

  private deliver(name: string, options: ComposerOpenOptions) {
    try {
      this.host.openWriter(name, options);
    } catch (error) {
      console.error(`[record-page] page.composer.open("${name}") — the host threw`, error);
    }
  }

  private refuseWindow(value: string, because: string) {
    if (import.meta.env.DEV)
      console.warn(
        `[record-page] page.composer.window = ${JSON.stringify(value)} — ${because}; nothing changed.`
      );
  }

  private refuse(name: string, because: string) {
    if (import.meta.env.DEV)
      console.warn(
        `[record-page] page.composer.open("${name}") — ${because}; nothing was opened.`
      );
    return false;
  }
}
