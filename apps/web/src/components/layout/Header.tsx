"use client";

import * as React from "react";
import Link from "next/link";
import { useTheme } from "next-themes";
import { Sun, Moon, Menu, X, ExternalLink } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function Header() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [mounted, setMounted] = React.useState(false);

  // Avoid hydration mismatch for theme icon
  React.useEffect(() => {
    setMounted(true);
  }, []);

  function toggleTheme() {
    setTheme(theme === "dark" ? "light" : "dark");
  }

  return (
    <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Logo / Brand */}
        <div className="flex items-center gap-2">
          <Link href="/" className="flex items-center gap-2">
            <span className="font-bold text-xl text-foreground">Kara</span>
            <span className="text-sm text-muted-foreground font-medium">कर</span>
          </Link>
          <Badge variant="secondary" className="hidden sm:inline-flex text-xs">
            Open Source
          </Badge>
        </div>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center gap-1" aria-label="Main navigation">
          <Link
            href="/"
            className="px-3 py-2 text-sm font-medium text-foreground/80 hover:text-foreground hover:bg-accent rounded-md transition-colors"
          >
            Home
          </Link>
          <Link
            href="/chat"
            className="px-3 py-2 text-sm font-medium text-foreground/80 hover:text-foreground hover:bg-accent rounded-md transition-colors"
          >
            Chat
          </Link>

          {/* Dark mode toggle */}
          <Button
            variant="ghost"
            size="icon"
            className="min-w-[44px] min-h-[44px]"
            onClick={toggleTheme}
            aria-label={mounted && resolvedTheme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {mounted ? (
              resolvedTheme === "dark" ? (
                <Sun className="h-4 w-4" />
              ) : (
                <Moon className="h-4 w-4" />
              )
            ) : (
              <Moon className="h-4 w-4" />
            )}
          </Button>

          {/* GitHub link */}
          <a
            href="https://github.com/kara-project/kara"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="View on GitHub"
            className={cn(
              buttonVariants({ variant: "ghost", size: "icon" }),
              "min-w-[44px] min-h-[44px]"
            )}
          >
            <ExternalLink className="h-4 w-4" />
          </a>
        </nav>

        {/* Mobile: hamburger */}
        <div className="flex items-center md:hidden">
          <Button
            variant="ghost"
            size="icon"
            className="min-w-[44px] min-h-[44px]"
            onClick={() => setMenuOpen((prev) => !prev)}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            aria-controls="mobile-menu"
          >
            {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </div>

      {/* Mobile dropdown menu */}
      {menuOpen && (
        <div
          id="mobile-menu"
          role="navigation"
          aria-label="Mobile navigation"
          className="md:hidden border-t bg-background px-4 py-3 flex flex-col gap-1"
        >
          <Link
            href="/"
            className="flex items-center min-h-[44px] px-3 py-2 text-sm font-medium text-foreground/80 hover:text-foreground hover:bg-accent rounded-md transition-colors"
            onClick={() => setMenuOpen(false)}
          >
            Home
          </Link>
          <Link
            href="/chat"
            className="flex items-center min-h-[44px] px-3 py-2 text-sm font-medium text-foreground/80 hover:text-foreground hover:bg-accent rounded-md transition-colors"
            onClick={() => setMenuOpen(false)}
          >
            Chat
          </Link>
          <div className="flex items-center gap-2 pt-1 border-t mt-1">
            <Button
              variant="ghost"
              size="icon"
              className="min-w-[44px] min-h-[44px]"
              onClick={() => {
                toggleTheme();
                setMenuOpen(false);
              }}
              aria-label={mounted && resolvedTheme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {mounted ? (
                resolvedTheme === "dark" ? (
                  <Sun className="h-4 w-4" />
                ) : (
                  <Moon className="h-4 w-4" />
                )
              ) : (
                <Moon className="h-4 w-4" />
              )}
            </Button>
            <a
              href="https://github.com/kara-project/kara"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="View on GitHub"
              className={cn(
                buttonVariants({ variant: "ghost", size: "icon" }),
                "min-w-[44px] min-h-[44px]"
              )}
            >
              <ExternalLink className="h-4 w-4" />
            </a>
          </div>
        </div>
      )}
    </header>
  );
}
