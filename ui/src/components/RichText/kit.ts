/** The rich-text editor setup the Text Editor field and the composer share. */
import type { MaybeRefOrGetter } from "vue";
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

export const richTextToolbar = [
  Paragraph,
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
