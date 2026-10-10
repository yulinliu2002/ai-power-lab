import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

// Self-hosted (not next/font/google): the exact IBM Plex Sans/Mono latin
// .woff2 files Google Fonts serves for this app's weights, vendored once
// so `next build` never needs network access to fonts.googleapis.com.
// IBM Plex Sans is distributed by Google Fonts as a single variable-weight
// file (confirmed: the CSS2 API returns the identical file for weights
// 400/500/600/700), hence one `localFont` entry with a weight range; IBM
// Plex Mono is static per weight, hence one entry per weight.
const plexSans = localFont({
  src: "./fonts/ibm-plex-sans-latin-wght-variable.woff2",
  weight: "400 700",
  variable: "--font-plex-sans",
});

const plexMono = localFont({
  src: [
    { path: "./fonts/ibm-plex-mono-latin-400.woff2", weight: "400" },
    { path: "./fonts/ibm-plex-mono-latin-500.woff2", weight: "500" },
    { path: "./fonts/ibm-plex-mono-latin-600.woff2", weight: "600" },
  ],
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: "AI Power Lab",
  description: "SST / 800 VDC AI Power Infrastructure",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${plexSans.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-canvas text-primary font-sans">
        {children}
      </body>
    </html>
  );
}
