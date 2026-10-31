"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { ApiClient } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthContextValue {
  api: ApiClient;
  user: User | null;
  notice: string;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [api] = useState(
    () =>
      new ApiClient(
        process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api/v1",
      ),
  );
  const [user, setUser] = useState<User | null>(null);
  const [notice, setNotice] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const expire = useCallback(() => {
    clearTimeout(timer.current);
    api.setToken(null);
    setUser(null);
    setNotice(
      "Your session has expired or been revoked. Please sign in again.",
    );
    router.replace("/login");
  }, [api, router]);
  useEffect(() => {
    api.setUnauthorizedHandler(expire);
    document.body.dataset.appReady = "true";
    return () => {
      api.setUnauthorizedHandler(undefined);
      clearTimeout(timer.current);
      delete document.body.dataset.appReady;
    };
  }, [api, expire]);
  async function login(email: string, password: string) {
    const response = await api.login(email.trim(), password);
    api.setToken(response.access_token);
    try {
      const current = await api.me();
      setUser(current);
      setNotice("");
      clearTimeout(timer.current);
      timer.current = setTimeout(expire, response.expires_in * 1000);
      router.replace("/dashboard");
    } catch (error) {
      api.setToken(null);
      throw error;
    }
  }
  async function logout() {
    await api.logout(); // Only claim server revocation after a successful response.
    clearTimeout(timer.current);
    api.setToken(null);
    setUser(null);
    setNotice("You have been signed out of all sessions.");
    router.replace("/login");
  }
  return (
    <AuthContext.Provider value={{ api, user, notice, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("AuthProvider is required");
  return context;
}
