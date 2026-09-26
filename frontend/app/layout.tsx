import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "TenantMind AI",
  description: "A secure, cited knowledge assistant for modern teams.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

