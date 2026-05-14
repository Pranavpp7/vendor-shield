import { useUser, useClerk } from "@clerk/clerk-react";

const clerkEnabled =
  !!import.meta.env.VITE_CLERK_PUBLISHABLE_KEY &&
  import.meta.env.VITE_CLERK_PUBLISHABLE_KEY !== "pk_test_replace_me";

type AuthState = {
  userId: string | null | undefined;
  isLoaded: boolean;
  isSignedIn: boolean | undefined;
  signOut: () => Promise<void>;
};

// Two separate hooks so we never call Clerk hooks conditionally.
function useClerkAuthState(): AuthState {
  const { user, isLoaded, isSignedIn } = useUser();
  const { signOut } = useClerk();
  return { userId: user?.id ?? null, isLoaded, isSignedIn, signOut: () => signOut() };
}

function useDevAuthState(): AuthState {
  return { userId: null, isLoaded: true, isSignedIn: true, signOut: async () => {} };
}

// useAuth is fixed at module-load time — no conditional hook calls at runtime.
export const useAuth: () => AuthState = clerkEnabled ? useClerkAuthState : useDevAuthState;
