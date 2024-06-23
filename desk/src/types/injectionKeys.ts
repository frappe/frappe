import type { InjectionKey } from "vue"
import type { ModuleSidebarItem, UpdateSidebarItemAction } from "@/types"

export const updateSidebarItemFnKey = Symbol("updateSidebarItem") as InjectionKey<
	(item: ModuleSidebarItem, action: UpdateSidebarItemAction) => void
>
