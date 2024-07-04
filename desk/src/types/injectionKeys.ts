import type { InjectionKey } from "vue"
import type { ModuleSidebarItem, UpdateSidebarItemAction } from "@/types"

export const updateSidebarItemFnKey = Symbol("updateSidebarItem") as InjectionKey<
	(item: ModuleSidebarItem, action: UpdateSidebarItemAction) => void
>

export const fetchListFnKey = Symbol("fetchList") as InjectionKey<
	(updateCount?: boolean) => Promise<void>
>
