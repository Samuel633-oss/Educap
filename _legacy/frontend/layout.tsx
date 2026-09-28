import "./globals.css";
import type { Metadata } from "next";
import { Bricolage_Grotesque, Newsreader } from "next/font/google";

const ui = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-ui" });
const read = Newsreader({ subsets: ["latin"], variable: "--font-read" });

export const metadata: Metadata = { title: "Educap", description: "A team of AI tutors that adapts to how you learn." };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en" className={`${ui.variable} ${read.variable}`}><body>{children}</body></html>;
}
