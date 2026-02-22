import { ReactNode } from "react";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "./AppSidebar";

export function AppLayout({ children }: { children: ReactNode }) {
  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        <AppSidebar />
        <div className="flex-1 flex flex-col min-h-screen">
          <header className="h-14 border-b bg-card/80 backdrop-blur-sm flex items-center px-4 sticky top-0 z-50">
            <SidebarTrigger className="mr-4" />
          </header>
          <main className="flex-1 p-6 lg:p-8 bg-background">{children}</main>
        </div>
      </div>
    </SidebarProvider>
  );
}
