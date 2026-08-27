import type { ReactNode } from "react";

// Shared visual shell for /login and /console/login — grid-line texture
// background + brand mark, per design_handoff_dashboard_redesign. The
// mockup's login page fakes a tab-switch between Lab/Root sign-in with one
// shared route; the real app keeps them as separate routes (/login vs
// /console/login) as it already did, so there's no tab control here.
export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4">
      <div className="hs-grid-bg absolute inset-0" />
      <div className="relative z-10 w-full max-w-sm">{children}</div>
    </main>
  );
}

export function BrandMark() {
  return (
    <div className="mb-7 flex items-center gap-2.5">
      <div className="flex h-[34px] w-[34px] items-center justify-center rounded-lg bg-accent font-mono font-bold text-accent-foreground">
        &gt;_
      </div>
      <div className="text-[17px] font-extrabold tracking-tight">
        HSLab <span className="font-semibold text-muted">CTF</span>
      </div>
    </div>
  );
}
