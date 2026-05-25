import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PolicyLens AI — Insurance Intelligence Platform",
  description:
    "Understand your insurance policies instantly. AI-powered policy analysis with clause-grounded answers, eligibility checking, exclusion detection, and policy comparison.",
  keywords: [
    "insurance",
    "policy analysis",
    "AI",
    "eligibility checker",
    "exclusions",
    "claim assistance",
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
