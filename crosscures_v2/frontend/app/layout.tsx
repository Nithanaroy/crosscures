import type { Metadata } from "next";
import "./globals.css";
import StoreHydration from "@/components/StoreHydration";

export const metadata: Metadata = {
  title: "CrossCures — AI Health Companion",
  description: "Your intelligent health companion for personalized care, clinic visits, and therapy monitoring.",
  keywords: ["health", "AI", "medical", "patient", "physician"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-slate-50 antialiased" suppressHydrationWarning>
        <StoreHydration />
        {children}
      </body>
    </html>
  );
}
