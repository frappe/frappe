// The form fills the column with no border of its own, and its strip stays put while the sections scroll.
// The strip and the sections share the header row's gutter, so the fields line up with the crumbs.
import { TAB_STRIP_CLASSES } from "./tabs/recordTabs";

export const FORM_CLASSES = [
	"!rounded-none !border-0",
	"[&_[role='tablist']]:sticky [&_[role='tablist']]:top-0 [&_[role='tablist']]:z-10 [&_[role='tablist']]:bg-surface-base",
	TAB_STRIP_CLASSES,
	"[&_.sections]:mx-auto [&_.sections]:my-0 [&_.sections]:w-full [&_.sections]:max-w-3xl [&_.sections]:px-[--page-gutter] [&_.sections]:py-6",
	"[&_.section-header]:!px-0 [&_.section-body]:!px-0",
];
