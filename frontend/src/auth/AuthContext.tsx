import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { getCurrentUser, login as loginRequest } from "../api/auth";
import { ApiError, type User } from "../api/client";

const tokenStorageKey = "wcdms.access-token";

type AuthContextValue = {
  isLoading: boolean;
  token: string | null;
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => sessionStorage.getItem(tokenStorageKey));
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(() => {
    sessionStorage.removeItem(tokenStorageKey);
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    if (!token) {
      setIsLoading(false);
      return;
    }
    void getCurrentUser(token)
      .then(setUser)
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) {
          logout();
        }
      })
      .finally(() => setIsLoading(false));
  }, [logout, token]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await loginRequest(email, password);
    sessionStorage.setItem(tokenStorageKey, response.access_token);
    setToken(response.access_token);
    setUser(response.user);
  }, []);

  const value = useMemo(
    () => ({ isLoading, token, user, login, logout }),
    [isLoading, token, user, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider.");
  }
  return context;
}
