import { inject, onUnmounted, provide } from "vue";
import type { InjectionKey, Ref, ShallowRef } from "vue";
import type { WindowMode } from "frappe-ui/experimental";

/** What a channel's editable content contributes to the window chrome: a
 *  plain-text draft preview for the collapsed trigger, and focus-on-open. */
export interface ChannelSurface {
  preview: () => string;
  focus: () => void;
}

/** A channel registered by <ComposerChannel>. `surface` is filled in by the
 *  content mounted inside it (via useComposerSurface). */
export interface ChannelEntry {
  value: string;
  label: string;
  surface: ChannelSurface | null;
}

export interface ComposerContext {
  open: Ref<boolean>;
  channel: Ref<string>;
  mode: Ref<WindowMode>;
  channels: ShallowRef<ChannelEntry[]>;
  register: (entry: ChannelEntry) => void;
  unregister: (value: string) => void;
  /** When false, the window is always open — no trigger, no minimizing. */
  minimizable: Ref<boolean>;
  /** Collapse the window back to its trigger (no-op when not minimizable). */
  close: () => void;
  /** The persistent wrapper around trigger + window (drag pointer capture). */
  rootElement: Ref<HTMLElement | null>;
  /** Set when a resize drag ends collapsed; ComposerTrigger swallows the
   *  click the browser synthesizes right after. */
  dragCollapsedAt: Ref<number>;
}

const composerKey: InjectionKey<ComposerContext> = Symbol("Composer");
const channelKey: InjectionKey<(surface: ChannelSurface | null) => void> =
  Symbol("ComposerChannel");

/** Called by <Composer> to make its state available to the other parts. */
export function provideComposer(context: ComposerContext) {
  provide(composerKey, context);
}

/** The enclosing Composer's context, if any (null when rendered standalone). */
export function injectComposer(): ComposerContext | null {
  return inject(composerKey, null);
}

/** For parts that cannot work outside the root (Trigger, Content). */
export function requireComposer(part: string): ComposerContext {
  const composer = injectComposer();
  if (!composer) throw new Error(`<${part}> must be used inside <Composer>`);
  return composer;
}

/** Called by <ComposerChannel> so content below it can hand up its surface. */
export function provideChannelSurfaceSetter(
  set: (surface: ChannelSurface | null) => void
) {
  provide(channelKey, set);
}

/**
 * Called by channel content (EmailComposer, CommentComposer, custom editors)
 * to hand its draft preview + focus to the enclosing <ComposerChannel>.
 * A no-op when rendered outside one (inline usage).
 */
export function useComposerSurface(surface: ChannelSurface) {
  const setSurface = inject(channelKey, null);
  if (!setSurface) return;
  setSurface(surface);
  onUnmounted(() => setSurface(null));
}
