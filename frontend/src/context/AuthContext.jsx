import { createContext, useContext, useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../axios';

const AuthContext = createContext();
let profileRequest = null;

export const AuthProvider = ({ children }) => {
    const navigate = useNavigate();
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const authVersion = useRef(0);

    const fetchProfile = async () => {
        const requestVersion = authVersion.current;
        if (!profileRequest) {
            profileRequest = api.get('/profile/')
                .then((response) => response.data)
                .catch(() => null)
                .finally(() => {
                    profileRequest = null;
                });
        }
        try {
            const profile = await profileRequest;
            if (requestVersion === authVersion.current) setUser(profile);
            return profile;
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        const handleUnauthorized = () => {
            authVersion.current += 1;
            setUser(null);
            setLoading(false);
        };
        window.addEventListener('auth:unauthorized', handleUnauthorized);
        fetchProfile();
        return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
    }, []);

    const login = async (username, password) => {
        const response = await api.post('/api/login/', { username, password });
        authVersion.current += 1;
        setUser(response.data);
        setLoading(false);
        return response.data;
    };

    const signup = async (userData) => {
        const response = await api.post('/api/signup/', userData);
        return response.data;
    };

    const logout = async () => {
        try {
            await api.post('/logout/', {}, { withCredentials: true });
        } catch {
        } finally {
            authVersion.current += 1;
            setUser(null);
            setLoading(false);
            navigate('/', { replace: true });
        }
    };

    const value = {
        user,
        loading,
        login,
        signup,
        logout,
        refreshUser: fetchProfile,
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
