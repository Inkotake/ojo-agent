import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: number;
  username: string;
  role: 'user' | 'admin';
  email: string;
  status: string;
}

interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  
  login: (token: string, user: User) => void;
  logout: () => void;
  checkAuth: () => Promise<boolean>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      isAdmin: false,

      login: (token, user) => {
        set({
          token,
          user,
          isAuthenticated: true,
          isAdmin: user.role === 'admin'
        });
      },

      logout: () => {
        set({
          token: null,
          user: null,
          isAuthenticated: false,
          isAdmin: false
        });
      },

      checkAuth: async () => {
        const { token } = get();
        if (!token) return false;

        try {
          // Use relative path since frontend and API are on the same server
          const response = await fetch('/api/auth/check', {
            headers: {
              'Authorization': `Bearer ${token}`
            }
          });

          if (!response.ok) {
            get().logout();
            return false;
          }

          return true;
        } catch (error) {
          get().logout();
          return false;
        }
      }
    }),
    {
      name: 'auth-storage'
    }
  )
);
