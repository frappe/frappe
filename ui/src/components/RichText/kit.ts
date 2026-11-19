/** The rich-text editor setup the Text Editor field and the composer share. */
import { ref } from "vue";
import type { MaybeRefOrGetter } from "vue";
import { Extension } from "@tiptap/core";
import {
  RichTextKit,
  Paragraph,
  H2,
  H3,
  H4,
  Separator,
  Bold,
  Italic,
  FontColor,
  AlignLeft,
  AlignCenter,
  AlignRight,
  BulletList,
  OrderedList,
  InsertImage,
  InsertVideo,
  InsertLink,
  Blockquote,
  InlineCode,
  HorizontalRule,
  InsertTable,
} from "frappe-ui/editor";
import type { MentionSuggestionItem } from "frappe-ui/editor";

/** The kit with no iframe. With no `mentions`, stored mentions draw but `@` opens no menu. */
export function richTextKit(mentions?: MaybeRefOrGetter<MentionSuggestionItem[]>) {
  return RichTextKit.configure({
    heading: { levels: [2, 3, 4, 5, 6] },
    mention: mentions ? { items: mentions } : {},
    // Server sanitizing drops iframes, so a pasted URL would become an embed lost on save.
    iframe: false,
  });
}

/** A toolbar key bumped once the view mounts: frappe-ui reads disabled states before the view
 * exists and then only on a transaction. Do not dispatch one instead: it rewrites stored HTML. */
export function useToolbarKey() {
  const key = ref(0);
  const extension = Extension.create({
    name: "toolbarKey",
    onCreate() {
      key.value++;
    },
  });
  return { key, extension };
}

export const richTextToolbar = [
  {
    ...Paragraph,
    // `setParagraph` cannot run in a paragraph, where the button is pressed.
    isDisabled: (editor) => !editor.isActive("paragraph") && Paragraph.isDisabled?.(editor) === true,
  } satisfies typeof Paragraph,
  H2,
  H3,
  H4,
  Separator,
  Bold,
  Italic,
  FontColor,
  Separator,
  AlignLeft,
  AlignCenter,
  AlignRight,
  BulletList,
  OrderedList,
  Separator,
  InsertImage,
  InsertVideo,
  InsertLink,
  Blockquote,
  InlineCode,
  HorizontalRule,
  InsertTable,
];

/** The bar over a selection in a panel row: no headings, so it fits inside the row's box. */
export const richTextBubble = [Bold, Italic, InsertLink, InlineCode, BulletList, OrderedList];
