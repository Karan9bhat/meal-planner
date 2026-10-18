import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";
import { AppHeader } from "@/components/AppHeader";
import { PlanProvider } from "@/lib/store";
import "./globals.css";

const display = Fraunces({ variable: "--nf-display", subsets: ["latin"], weight: ["500", "600", "700"] });
const body = Inter({ variable: "--nf-body", subsets: ["latin", "cyrillic"] });

export const metadata: Metadata = {
  title: "meal-planner — meals for your kitchen, anywhere",
  description:
    "A weekly meal plan built around where you live, the food you grew up with, what's in your kitchen and what you can spend. Powered by open-weight AI.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${display.variable} ${body.variable} font-sans antialiased`}>
        <PlanProvider>
          <AppHeader />
          {children}
        </PlanProvider>
      </body>
    </html>
  );
}
