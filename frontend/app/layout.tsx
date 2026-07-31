import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { Providers } from "./providers";

const spaceGrotesk = localFont({
  src: "../public/fonts/SpaceGrotesk.woff2",
  variable: "--font-space-grotesk",
  weight: "100 900",
  display: "swap",
});

const sora = localFont({
  src: "../public/fonts/Sora.woff2",
  variable: "--font-sora",
  weight: "100 800",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Bria Exchange — AI Content Verification",
  description: "Independent AI content verification platform. Verify AI-generated content against vetted, licensed sources.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${spaceGrotesk.variable} ${sora.variable} antialiased`}
      >
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
