import { Badge } from "@/components/ui/badge";

export function Footer() {
  return (
    <footer className="border-t bg-background py-6 px-4">
      <div className="mx-auto max-w-7xl flex flex-col items-center gap-3 text-center sm:flex-row sm:justify-between sm:text-left">
        <p className="text-sm text-muted-foreground">
          Kara (कर) — Open Source AI Tax Advisor for India
        </p>

        <div className="flex flex-col items-center gap-3 sm:flex-row sm:gap-4">
          <nav className="flex items-center gap-4" aria-label="Footer navigation">
            <a
              href="https://github.com/kara-project/kara"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              GitHub
            </a>
            <a
              href="#"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Documentation
            </a>
          </nav>
          <Badge variant="secondary" className="text-xs">
            MIT License
          </Badge>
        </div>
      </div>
    </footer>
  );
}
