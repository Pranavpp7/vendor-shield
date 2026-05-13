import { useLocation } from "react-router-dom";
import { LayoutDashboard, ClipboardList, PlusCircle, Shield, Info, Settings, BarChart2 } from "lucide-react";
import { NavLink } from "@/components/NavLink";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarHeader,
} from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";

const navItems = [
  { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard },
  { title: "Assessments", url: "/assessments", icon: ClipboardList },
  { title: "New Assessment", url: "/assessment/new", icon: PlusCircle },
  { title: "Compare", url: "/compare", icon: BarChart2 },
  { title: "Architecture", url: "/architecture", icon: Info },
  { title: "Settings", url: "/settings", icon: Settings },
];

export function AppSidebar() {
  const location = useLocation();

  return (
    <Sidebar className="border-r border-sidebar-border">
      <SidebarHeader className="p-5">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent/10">
            <Shield className="h-6 w-6 text-accent" />
          </div>
          <div>
            <h2 className="font-bold text-base text-sidebar-foreground">Vendor Shield</h2>
            <p className="text-[11px] text-muted-foreground leading-tight">Vendor Risk Platform</p>
          </div>
        </div>
      </SidebarHeader>

      <Separator className="mx-4 w-auto" />

      <SidebarContent className="px-3 pt-4">
        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] uppercase tracking-widest text-muted-foreground/70 mb-1">
            Navigation
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild>
                    <NavLink
                      to={item.url}
                      end
                      className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors hover:bg-sidebar-accent"
                      activeClassName="bg-sidebar-accent text-accent font-semibold"
                    >
                      <item.icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

    </Sidebar>
  );
}
