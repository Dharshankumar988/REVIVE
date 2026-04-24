import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "REVIVE Dashboard",
  description: "Real-time Evaluation of Vitals & Intelligent Virtual Emergency Support",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
