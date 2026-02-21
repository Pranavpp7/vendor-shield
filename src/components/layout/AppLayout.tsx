import { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Shield, LogOut } from "lucide-react";

export function AppLayout({ children }: { children: ReactNode }) {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card sticky top-0 z-50">
        <div className="container flex items-center justify-between h-16">
          <Link to="/dashboard" className="flex items-center gap-2">
            <Shield className="h-6 w-6 text-accent" />
            <span className="font-bold text-lg">Bank ABC</span>
            <span className="text-xs text-muted-foreground hidden sm:inline ml-1">
              Vendor Risk Assessments
            </span>
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">Security Assessor</span>
            <Button variant="ghost" size="sm" onClick={() => navigate("/")}>
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>
      <main className="container py-8">{children}</main>
    </div>
  );
}
