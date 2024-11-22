import { AvatarCardProps } from "./AvatarCard"

export interface CardListProps {
	title?: string,
	cards: AvatarCardProps[]
	rowKey?: string
}

export interface CardListEmits {
	(event: 'onRowClick', card: AvatarCardProps): void
}