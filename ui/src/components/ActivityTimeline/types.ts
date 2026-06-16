export interface ActivityTimelineProps {
	doctype: string
	docname: string
	/** Chronological order of the feed. 'desc' (default) = newest at top (desk form
	 * timeline); 'asc' = oldest at top (Helpdesk chat-style). */
	order?: 'asc' | 'desc'
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

export interface AttachmentLogActivity {
	type: 'attachment_log'
	key: string
	name: string
	timestamp: string
	action: 'added' | 'removed'
	fileName: string
	fileUrl?: string
	isPrivate: boolean
	author: UserInfo
}

export interface AuditActivity {
	type: 'audit'
	key: string
	name: string
	timestamp: string
	subtype: 'like' | 'assigned' | 'assignment_completed' | 'workflow' | 'info'
	/** lucide icon name (no prefix) */
	icon: string
	/** final display string */
	text: string
	author: UserInfo
}

export type Activity =
	| EmailActivity
	| CommentActivity
	| AttachmentLogActivity
	| AuditActivity

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
	like_logs?: DocinfoComment[]
	attachment_logs?: DocinfoComment[]
	assignment_logs?: DocinfoComment[]
	workflow_logs?: DocinfoComment[]
	info_logs?: DocinfoComment[]
	user_info: Record<string, UserInfo>
}
