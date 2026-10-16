import type { Metadata } from "next";
import { Console } from "@/components/console";
import "@fontsource-variable/inter";
import "@xyflow/react/dist/style.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "KnowGraph — Engineering intelligence",
  description: "An evidence-backed company brain. Connect incidents, changes, people, and knowledge.",
  icons: { icon: "/icon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><Console>{children}</Console></body></html>;
}
