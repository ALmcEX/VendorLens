import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VendorLens — Evidence infrastructure for vendor review",
  description: "A production-style foundation for traceable AI SaaS vendor review workflows.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
