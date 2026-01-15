from typing import Literal, TypedDict


# Set/Notification/Email Action blocks
class SetAction(TypedDict):
	type: Literal["set"]
	field: str
	value: str


class EmailAction(TypedDict, total=False):
	type: Literal["email"]
	to: str
	via: Literal["rich_text", "template"]
	template: str
	doctype: str
	subject: str
	message: str
	create_communication: bool


class NotificationAction(TypedDict, total=False):
	type: Literal["notification"]
	# Add notification-specific fields here


AutomationAction = SetAction | EmailAction | NotificationAction


# IF and ELSE blocks
class IfBlock(TypedDict):
	type: Literal["if"]
	conditions: list[list[str] | str]
	actions: list["AutomationAction"]


class ElseBlock(TypedDict):
	type: Literal["else"]
	conditions: str
	actions: list["AutomationAction"]


# Top-level rule block
AutomationRuleBlock = IfBlock | ElseBlock | SetAction | EmailAction | NotificationAction


class AutomationRuleJSON(TypedDict):
	presets: list[list[str] | str]
	rule: list[AutomationRuleBlock]
