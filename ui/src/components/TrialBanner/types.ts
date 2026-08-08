/** Props for `<TrialBanner>`. */
export interface TrialBannerProps {
  /** Render the collapsed, icon-only form used by a collapsed sidebar. */
  isSidebarCollapsed?: boolean;
  /** Run after the user is sent to Frappe Cloud to upgrade. */
  afterUpgrade?: () => void;
}

/** Shape of `frappecloud_billing.current_site_info`. */
export interface SiteInfo {
  /** ISO date the trial ends on. */
  trial_end_date?: string;
  /** Frappe Cloud dashboard origin, e.g. `https://frappecloud.com`. */
  base_url: string;
  /** Site the dashboard link points at. */
  site_name: string;
  plan: { is_trial_plan: boolean };
}
