import { SignIn } from "@clerk/clerk-react";
import { Navigate } from "react-router-dom";

const clerkEnabled =
  !!import.meta.env.VITE_CLERK_PUBLISHABLE_KEY &&
  import.meta.env.VITE_CLERK_PUBLISHABLE_KEY !== "pk_test_replace_me";

const Login = () => {
  if (!clerkEnabled) return <Navigate to="/dashboard" replace />;
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <SignIn routing="path" path="/login" />
    </div>
  );
};

export default Login;
