import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);

  const refresh = useCallback(() => api.get("/auth/me").then((r) => { setUser(r.data); return r.data; }).catch(() => { setUser(false); return false; }), []);
  useEffect(() => { refresh(); }, [refresh]);

  const login = async (email, password) => { await api.post("/auth/login", { email, password }); return refresh(); };
  const signup = async (body) => { await api.post("/auth/signup", body); return refresh(); };
  const logout = async () => { await api.post("/auth/logout").catch(() => {}); setUser(false); };

  return <AuthContext.Provider value={{ user, login, signup, logout, refresh }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
export const homeFor = (u) => (u?.role === "platform_admin" ? "/platform" : "/admin");
