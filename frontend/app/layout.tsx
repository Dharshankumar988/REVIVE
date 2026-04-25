import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "REVIVE Dashboard",
  description: "Real-time Evaluation of Vitals & Intelligent Virtual Emergency Support",
  icons: {
    icon: [{ url: "/revive-mark.svg", type: "image/svg+xml" }],
    shortcut: "/revive-mark.svg",
    apple: "/revive-mark.svg",
  },
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
