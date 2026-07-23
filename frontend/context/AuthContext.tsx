"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

interface User {
  username: string;
  role: string;
}

interface AuthContextType {
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
  login: (username: string, password: string) => Promise<any>;
  logout: () => void;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // ========================
  // INIT (CEK TOKEN SEKALI)
  // ========================
  useEffect(() => {
    const storedToken = localStorage.getItem("auth_token");

    if (!storedToken) {
      setLoading(false);
      return;
    }

    verifyToken(storedToken);
  }, []);

  // ========================
  // VERIFY TOKEN (FIXED)
  // ========================
  const verifyToken = async (tokenToVerify: string) => {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 1500); // lebih cepat

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "/api"}/auth/verify`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${tokenToVerify}`,
        },
        signal: controller.signal,
      });

      clearTimeout(timeout);

      if (!response.ok) throw new Error("Invalid token");

      const data = await response.json();

      setUser({
        username: data.username,
        role: data.role,
      });
      setToken(tokenToVerify);
      setIsAuthenticated(true);

    } catch (err) {
      console.log("Token invalid / expired");

      localStorage.removeItem("auth_token");
      setUser(null);
      setToken(null);
      setIsAuthenticated(false);

    } finally {
      setLoading(false);
    }
  };

  // ========================
  // LOGIN (OPTIMIZED)
  // ========================
  const login = async (username: string, password: string) => {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "/api"}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      throw new Error(data?.detail || data?.message || "Login failed");
    }

    // langsung set tanpa verify ulang (biar cepat)
    setToken(data.access_token);
    setUser({
      username: data.username,
      role: data.role || "user",
    });
    setIsAuthenticated(true);

    localStorage.setItem("auth_token", data.access_token);

    return data;
  };

  // ========================
  // LOGOUT
  // ========================
  const logout = () => {
    setToken(null);
    setUser(null);
    setIsAuthenticated(false);
    localStorage.removeItem("auth_token");
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        user,
        token,
        login,
        logout,
        loading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ========================
// CUSTOM HOOK
// ========================
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}