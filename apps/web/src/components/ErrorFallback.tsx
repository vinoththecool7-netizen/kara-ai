"use client";

import { AlertTriangle, RefreshCw, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface ErrorFallbackProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
  onReload?: () => void;
  digest?: string;
}

export function ErrorFallback({
  title = "Something went wrong",
  description = "An unexpected error occurred while rendering this section.",
  onRetry,
  onReload,
  digest,
}: ErrorFallbackProps) {
  const isDev = process.env.NODE_ENV !== "production";
  return (
    <Card role="alert" className="border-destructive/30 bg-destructive/5">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-destructive">
          <AlertTriangle className="size-5" aria-hidden="true" />
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          {onRetry && (
            <Button onClick={onRetry} variant="default" size="sm">
              <RotateCcw className="size-4" aria-hidden="true" />
              Try again
            </Button>
          )}
          {onReload && (
            <Button onClick={onReload} variant="outline" size="sm">
              <RefreshCw className="size-4" aria-hidden="true" />
              Reload page
            </Button>
          )}
        </div>
        {isDev && digest && (
          <p className="text-xs text-muted-foreground font-mono">
            digest: {digest}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
