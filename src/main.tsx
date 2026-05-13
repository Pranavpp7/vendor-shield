import { createRoot } from "react-dom/client";
import { ClerkProvider, useAuth } from "@clerk/clerk-react";
import App from "./App.tsx";
import "./index.css";
import { setTokenGetter } from "@/lib/api";

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string;

function AuthBridge() {
  const { getToken } = useAuth();
  setTokenGetter(getToken);
  return null;
}

function Root() {
  if (!PUBLISHABLE_KEY || PUBLISHABLE_KEY === "pk_test_replace_me") {
    return <App />;
  }
  return (
    <ClerkProvider publishableKey={PUBLISHABLE_KEY} afterSignOutUrl="/login">
      <AuthBridge />
      <App />
    </ClerkProvider>
  );
}

createRoot(document.getElementById("root")!).render(<Root />);
