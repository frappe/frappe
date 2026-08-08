/** Props for `<SignupBanner>`. */
export interface SignupBannerProps {
  /** Render the collapsed, icon-only form used by a collapsed sidebar. */
  isSidebarCollapsed?: boolean;
  /** App name used in the default banner copy. */
  appName?: string;
  /** Signup page opened in a new tab when the button is clicked. */
  redirectURL?: string;
  /** Run after the signup page is opened. */
  afterSignup?: () => void;
}
