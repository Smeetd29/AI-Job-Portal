import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const ProtectedRoute = ({ allowedRoles }) => {
    const { user, loading } = useAuth();

    if (loading) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-gray-50">
                <div className="text-sm font-medium text-gray-500">Verifying session...</div>
            </div>
        );
    }

    if (!user) return <Navigate to="/login" replace />;
    if (allowedRoles && !allowedRoles.includes(user.is_recruiter ? 'recruiter' : 'candidate')) return <Navigate to="/" replace />;

    return <Outlet />;
};

export default ProtectedRoute;
