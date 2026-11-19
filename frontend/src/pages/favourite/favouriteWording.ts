// The favourite toggle's label and icon, shared by the record's menu row and the list's act.
import { __ } from "@/i18n";

export function favouriteWording(favourited: boolean): { label: string; icon: string } {
	return favourited
		? { label: __("Remove from favourites"), icon: "lucide-star-off" }
		: { label: __("Add to favourites"), icon: "lucide-star" };
}
