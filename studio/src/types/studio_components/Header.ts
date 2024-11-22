export interface MenuItem {
	label: string
	action: () => void
}

export interface HeaderProps {
	title?: string
	logoSVG?: string
	hideLogo?: boolean
	menuItems?: MenuItem[]
	hideMenu?: boolean
}
