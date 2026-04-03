import { createContext, useContext, useState, useEffect } from 'react';
import api from '../services/api';

// Create Auth Context
const AuthContext = createContext(null);

// Provider Component
export function AuthProvider({ children }) {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [token, setToken] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Initialize auth state from localStorage
  useEffect(() => {
    const storedToken = localStorage.getItem('auth_token');
    const storedUser = localStorage.getItem('current_user');

    if (storedToken && storedUser) {
      setToken(storedToken);
      setCurrentUser(JSON.parse(storedUser));
      setIsLoggedIn(true);
    }

    setIsLoading(false);
  }, []);

  const login = (user, newToken) => {
    setCurrentUser(user);
    setToken(newToken);
    setIsLoggedIn(true);
    localStorage.setItem('auth_token', newToken);
    localStorage.setItem('current_user', JSON.stringify(user));
  };

  const logout = () => {
    setCurrentUser(null);
    setToken(null);
    setIsLoggedIn(false);
    localStorage.removeItem('auth_token');
    localStorage.removeItem('current_user');
  };

  const refreshUser = async () => {
    if (!token) return;

    try {
      const response = await api.get('/auth/me');
      const userData = response.data || response;
      setCurrentUser(userData);
      localStorage.setItem('current_user', JSON.stringify(userData));
    } catch (error) {
      console.error('Failed to refresh user data:', error);
    }
  };

  const isAdmin = currentUser?.is_admin || false;

  return (
    <AuthContext.Provider
      value={{
        isLoggedIn,
        currentUser,
        token,
        isLoading,
        isAdmin,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// Hook to use Auth Context
export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }

  return context;
}
