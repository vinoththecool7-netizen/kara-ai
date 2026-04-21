"use client";

interface GlobalErrorProps {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}

export default function GlobalError({ error, unstable_retry }: GlobalErrorProps) {
  const isDev = process.env.NODE_ENV !== "production";
  return (
    <html lang="en">
      <body
        style={{
          fontFamily:
            "system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0a0a0a",
          color: "#fafafa",
          padding: "2rem",
        }}
      >
        <main
          role="alert"
          style={{
            maxWidth: "32rem",
            display: "flex",
            flexDirection: "column",
            gap: "1rem",
            textAlign: "center",
          }}
        >
          <h1 style={{ fontSize: "1.75rem", fontWeight: 600, margin: 0 }}>
            Kara crashed
          </h1>
          <p style={{ margin: 0, opacity: 0.8 }}>
            Something went very wrong. Please reload the page.
          </p>
          <div
            style={{
              display: "flex",
              gap: "0.5rem",
              justifyContent: "center",
            }}
          >
            <button
              type="button"
              onClick={unstable_retry}
              style={{
                padding: "0.5rem 1rem",
                background: "#fafafa",
                color: "#0a0a0a",
                border: "none",
                borderRadius: "0.5rem",
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              Try again
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={{
                padding: "0.5rem 1rem",
                background: "transparent",
                color: "#fafafa",
                border: "1px solid #fafafa",
                borderRadius: "0.5rem",
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              Reload
            </button>
          </div>
          {isDev && error.digest && (
            <p
              style={{
                fontSize: "0.75rem",
                fontFamily: "ui-monospace, monospace",
                opacity: 0.6,
                margin: 0,
              }}
            >
              digest: {error.digest}
            </p>
          )}
        </main>
      </body>
    </html>
  );
}
