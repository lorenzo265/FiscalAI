import type { ReactNode } from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { SidebarMobile } from "@/components/layout/sidebar-mobile";
import { Topbar } from "@/components/layout/topbar";
import { AuthGuard } from "@/components/layout/auth-guard";
import { ChatFlutuante } from "@/components/assistente/chat-flutuante";
import { PageTransition } from "@/components/layout/page-transition";
import { LenisProvider } from "@/lib/motion";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <LenisProvider>
        <div className="flex min-h-screen">
          <Sidebar />
          <SidebarMobile />
          <div className="flex-1 flex flex-col min-w-0">
            <Topbar />
            <main className="flex-1 px-4 md:px-8 py-6 md:py-8">
              <div className="max-w-[1280px] mx-auto w-full">
                <PageTransition>{children}</PageTransition>
              </div>
            </main>
          </div>
          <ChatFlutuante />
        </div>
      </LenisProvider>
    </AuthGuard>
  );
}
