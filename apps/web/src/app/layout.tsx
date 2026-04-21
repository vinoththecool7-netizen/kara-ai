import type { Metadata, Viewport } from "next";
import { Geist_Mono } from "next/font/google";
import { ibmPlexSans } from "@/lib/fonts";
import { ThemeProvider } from "@/components/theme-provider";
import { SkipLink } from "@/components/layout/SkipLink";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { Toaster } from "@/components/ui/toast";
import { OfflineIndicator } from "@/components/OfflineIndicator";
import { SITE_URL } from "@/lib/constants";
import "./globals.css";

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const DESCRIPTION =
  "Open-source conversational AI tax advisor for Indian income tax. Get accurate computations, regime comparisons, and personalized advice.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Kara — AI Tax Advisor for India",
    template: "%s | Kara",
  },
  description: DESCRIPTION,
  applicationName: "Kara",
  keywords: [
    "India income tax",
    "tax advisor",
    "AI tax",
    "old vs new regime",
    "87A rebate",
    "FY 2025-26",
  ],
  authors: [{ name: "Kara Contributors" }],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: "/",
    siteName: "Kara",
    locale: "en_IN",
    title: "Kara — AI Tax Advisor for India",
    description: DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: "Kara — AI Tax Advisor for India",
    description: DESCRIPTION,
  },
  robots: { index: true, follow: true },
  category: "finance",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Kara",
  url: SITE_URL,
  applicationCategory: "FinanceApplication",
  operatingSystem: "Web",
  offers: { "@type": "Offer", price: 0, priceCurrency: "INR" },
  description: DESCRIPTION,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${ibmPlexSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <SkipLink />
          <OfflineIndicator />
          <Header />
          <main id="main-content" className="flex-1">
            {children}
          </main>
          <Footer />
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
