"use client";

import { useEffect } from "react";

import { ErrorFallback } from "@/components/ErrorFallback";

interface ErrorProps {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}

export default function Error({ error, unstable_retry }: ErrorProps) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto max-w-lg px-4 py-16">
      <ErrorFallback
        title="Something went wrong"
        description="Kara hit an unexpected error while loading this page."
        onRetry={unstable_retry}
        onReload={() => window.location.reload()}
        digest={error.digest}
      />
    </div>
  );
}
