import type { Metadata } from "next";
import { Sora, Source_Serif_4 } from "next/font/google";
import Script from "next/script";
import "./globals.css";

// Same Umami website as the landing page, so a visitor crossing from planlog.depak.dev to
// app.planlog.depak.dev stays one session. Absent unless configured.
const UMAMI_ID = process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID;
const UMAMI_HOST = process.env.NEXT_PUBLIC_UMAMI_HOST || "https://cloud.umami.is";

const sora = Sora({
  variable: "--font-sora",
  subsets: ["latin"],
});

const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Planlog",
  description:
    "Plan → Approve → Done — markdown plans humans and coding agents share. Agents read the plan before coding and post Done when they ship.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${sora.variable} ${sourceSerif.variable} h-full antialiased`}>
      <body className="min-h-full">
        {children}
        {UMAMI_ID && (
          <Script
            defer
            strategy="afterInteractive"
            src={`${UMAMI_HOST}/script.js`}
            data-website-id={UMAMI_ID}
          />
        )}
      </body>
    </html>
  );
}
