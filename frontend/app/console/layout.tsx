export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  // Theme is unified app-wide (see README §14, "Console theme" decision) — no
  // fixed dark skin here anymore. "System scope" is flagged by the ROOT /
  // SYSTEM SCOPE badge in the Console page's own topbar instead.
  return <div className="min-h-screen bg-background text-foreground">{children}</div>;
}
