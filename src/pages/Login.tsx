import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Shield } from "lucide-react";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    navigate("/dashboard");
  };

  return (
    <div className="min-h-screen flex">
      <div className="hidden lg:flex lg:w-1/2 bg-primary items-center justify-center p-12">
        <div className="max-w-md text-primary-foreground">
          <Shield className="h-16 w-16 mb-8 opacity-80" />
          <h1 className="text-4xl font-bold mb-4">Vendor Risk Assessment Platform</h1>
          <p className="text-lg opacity-80">
            Evaluate, monitor, and manage third-party vendor security risks with AI-powered assessments.
          </p>
        </div>
      </div>
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="flex items-center justify-center gap-2 mb-2 lg:hidden">
              <Shield className="h-8 w-8 text-accent" />
              <span className="font-bold text-xl">Bank ABC</span>
            </div>
            <CardTitle className="text-2xl">Sign In</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              Access the Vendor Risk Assessment Portal
            </p>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="assessor@bankabc.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              <Button type="submit" className="w-full">
                Sign In
              </Button>
              <p className="text-xs text-muted-foreground text-center">
                Mock login — any credentials accepted
              </p>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
