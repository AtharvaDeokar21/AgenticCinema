import { Bodoni_Moda, Courier_Prime } from "next/font/google";
import "./globals.css";

/* Bodoni Moda is a variable font, so no `weight` array is passed.
   Courier Prime is static, so its weights are declared explicitly. */
const display = Bodoni_Moda({
  subsets: ["latin"],
  style: ["normal", "italic"],
  display: "swap",
  variable: "--font-display",
});

const sheet = Courier_Prime({
  subsets: ["latin"],
  weight: ["400", "700"],
  style: ["normal", "italic"],
  display: "swap",
  variable: "--font-sheet",
});

export const metadata = {
  title: "CreatorCrew: seven agents, one crew",
  description:
    "An agentic production studio for solo creators. Finds the deal, times the script, plans the shot, syncs the audio, dubs it, and clears the rights before it costs a reshoot.",
};

export const viewport = {
  themeColor: "#0A0608",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${display.variable} ${sheet.variable}`}>
      <body>{children}</body>
    </html>
  );
}
