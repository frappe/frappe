// Desk's own after-save handlers: the person's name and image on screen, and one reload toast
// when a setting the page was drawn with changes.
import type { Session } from "@framework/ui/api";
import { askReload, registerAfterSave } from "@/afterSave";

const USER_RELOAD_FIELDS = ["language", "time_zone"];
const SYSTEM_RELOAD_FIELDS = [
	"time_zone",
	"date_format",
	"time_format",
	"number_format",
	"float_precision",
	"currency_precision",
	"first_day_of_the_week",
];

/** Updates `session.user` in place; `fetchBoot` makes it reactive. */
export function registerDeskAfterSave(session: Session): () => void {
	const removers = [
		registerAfterSave("User", (saved) => {
			if (saved.name !== session.user.name) return;
			session.user.full_name = saved.doc.full_name;
			session.user.user_image = saved.doc.user_image || null;
			session.user.document_follow_notify = Boolean(saved.doc.document_follow_notify);
			askReload(saved, USER_RELOAD_FIELDS);
		}),
		registerAfterSave("System Settings", (saved) => askReload(saved, SYSTEM_RELOAD_FIELDS)),
	];
	return () => removers.forEach((remove) => remove());
}
