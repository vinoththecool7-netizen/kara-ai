import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OGImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: "linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "32px",
        }}
      >
        <div
          style={{
            width: "120px",
            height: "120px",
            background: "rgba(255, 255, 255, 0.1)",
            borderRadius: "20px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <span
            style={{
              fontSize: "72px",
              fontWeight: "bold",
              color: "white",
              fontFamily: "system-ui",
            }}
          >
            K
          </span>
        </div>
        <div style={{ textAlign: "center", display: "flex", flexDirection: "column" }}>
          <h1
            style={{
              fontSize: "60px",
              fontWeight: "bold",
              color: "white",
              margin: "0 0 16px 0",
              fontFamily: "system-ui",
            }}
          >
            Kara
          </h1>
          <p
            style={{
              fontSize: "32px",
              color: "rgba(255, 255, 255, 0.9)",
              margin: "0",
              fontFamily: "system-ui",
            }}
          >
            AI Tax Advisor for India
          </p>
        </div>
      </div>
    ),
    { width: 1200, height: 630 },
  );
}
