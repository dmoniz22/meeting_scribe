import SidebarLayout from "./components/SidebarLayout";
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MeetScribe - AI Meeting Assistant",
  description: "Record, transcribe, and summarize your meetings with AI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <SidebarLayout>{children}</SidebarLayout>
      </body>
    </html>
  );
}
