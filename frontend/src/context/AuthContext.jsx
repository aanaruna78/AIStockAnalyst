import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { fetchUser } from '../services/api';

const AuthContext = createContext(null);

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    const loadUser = useCallback(async () => {
        const token = localStorage.getItem('token');
        if (!token) {
            setUser(null);
            setLoading(false);
            return;
        }
        try {
            const data = await fetchUser();
            setUser(data);
        } catch {
            localStorage.removeItem('token');
            setUser(null);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadUser();
    }, [loadUser]);

    const login = useCallback((token, userData) => {
        localStorage.setItem('token', token);
        setUser(userData);
    }, []);

    const logout = useCallback(() => {
        localStorage.removeItem('token');
        localStorage.removeItem('user_preferences');
        setUser(null);
    }, []);

    const updateUser = useCallback((userData) => {
        setUser(prev => ({ ...prev, ...userData }));
    }, []);

    return (
        <AuthContext.Provider value={{ user, loading, login, logout, updateUser, loadUser }}>
            {children}
        </AuthContext.Provider>
    );
};
