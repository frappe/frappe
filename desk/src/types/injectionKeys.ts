import type { InjectionKey } from "vue"
import type { ModuleSidebarLink, UpdateSidebarItemAction } from "@/types"

export const updateSidebarItemFnKey = Symbol("updateSidebarItem") as InjectionKey<
	(item: ModuleSidebarLink, action: UpdateSidebarItemAction) => void
>
