// The email field now lives in frappe-ui as `MultiEmailInput`
// (`frappe-ui/experimental`); the old local EmailMultiSelect + parseEmails were
// removed in favour of it.
export { default as InviteUser } from "./InviteUser.vue";
export { useInviteUser } from "./useInviteUser";
export type {
  RoleOption,
  UserOption,
  PendingInvitation,
  InviteResult,
  UseInviteUserOptions,
  InviteStore,
  InviteUserProps,
  InviteEmailSlotProps,
  InviteRolesSlotProps,
  InviteSubmitSlotProps,
} from "./types";
