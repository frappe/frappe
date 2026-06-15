export interface ActivityTimelineProps {
	doctype: string
	docname: string
	/** Stylesheet injected into the email iframe; auto-detected from the page when absent */
	cssHref?: string
	/** Current logged-in user email; used to compute reply/reply-all recipients */
	currentUser?: string
}

export interface UserInfo {
	email?: string
	fullname?: string
	image?: string
	name?: string
}

export interface EmailAttachment {
	file_url: string
	is_private?: 0 | 1
	file_name?: string
}

export interface EmailActivity {
	type: 'email'
	key: string
	name: string
	timestamp: string
	subject: string
	sender: string
	senderFullName: string
	senderImage?: string
	to: string
	cc: string
	bcc: string
	content: string
	deliveryStatus: string
	attachments: EmailAttachment[]
}

export interface CommentActivity {
	type: 'comment'
	key: string
	name: string
	timestamp: string
	content: string
	author: UserInfo
}

export type Activity = EmailActivity | CommentActivity

export interface EmailReplyPayload {
	content: string
	to: string
	cc?: string[]
	bcc?: string[]
}

export interface DocinfoComment {
	name: string
	creation: string
	content: string
	owner: string
	comment_type: string
	published: 0 | 1
}

export interface DocinfoCommunication {
	name: string
	communication_type: string
	communication_medium: string
	communication_date: string
	content: string
	sender: string
	sender_full_name: string
	cc: string
	bcc: string
	creation: string
	subject: string
	delivery_status: string
	recipients: string
	attachments?: string | EmailAttachment[]
}

export interface Docinfo {
	comments: DocinfoComment[]
	communications: DocinfoCommunication[]
	automated_messages: DocinfoCommunication[]
	user_info: Record<string, UserInfo>
}
