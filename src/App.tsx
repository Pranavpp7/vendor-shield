import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AssessmentProvider } from "@/context/AssessmentContext";
import { SignedIn, SignedOut, RedirectToSignIn } from "@clerk/clerk-react";
import Dashboard from "./pages/Dashboard";
import Assessments from "./pages/Assessments";
import NewAssessment from "./pages/NewAssessment";
import AssessmentDetail from "./pages/AssessmentDetail";
import Compare from "./pages/Compare";
import NotFound from "./pages/NotFound";
import Architecture from "./pages/Architecture";
import SettingsPage from "./pages/Settings";
import Login from "./pages/Login";

// When VITE_CLERK_PUBLISHABLE_KEY is unset or placeholder, all routes are
// accessible without login (dev mode — backend also skips auth).
const clerkEnabled =
  !!import.meta.env.VITE_CLERK_PUBLISHABLE_KEY &&
  import.meta.env.VITE_CLERK_PUBLISHABLE_KEY !== "pk_test_replace_me";

// Clerk's SignedIn/SignedOut only render when inside a ClerkProvider.
// When clerkEnabled=false we never render them, so ClerkProvider is not needed.
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  if (!clerkEnabled) return <>{children}</>;
  return (
    <>
      <SignedIn>{children}</SignedIn>
      <SignedOut><RedirectToSignIn /></SignedOut>
    </>
  );
};

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <AssessmentProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/login/*" element={<Login />} />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/assessments" element={<ProtectedRoute><Assessments /></ProtectedRoute>} />
            <Route path="/assessment/new" element={<ProtectedRoute><NewAssessment /></ProtectedRoute>} />
            <Route path="/assessments/:vendorSlug" element={<ProtectedRoute><AssessmentDetail /></ProtectedRoute>} />
            <Route path="/compare" element={<ProtectedRoute><Compare /></ProtectedRoute>} />
            <Route path="/architecture" element={<ProtectedRoute><Architecture /></ProtectedRoute>} />
            <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </AssessmentProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
