import { ChatWidget } from "@/components/ChatWidget";

export default function PlanLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <>
      <main className="mx-auto max-w-6xl px-4 pb-10 pt-6 sm:px-6">{children}</main>
      <ChatWidget />
    </>
  );
}
