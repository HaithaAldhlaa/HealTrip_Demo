import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HealTrip AI Patient Decision Assistant",
  description:
    "Prototype decision-support assistant: bilingual chat, one AI agent, tool-calling grounded on verified demo providers.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}