import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Briefcase, User, LogOut, LayoutDashboard, Menu, X, Sparkles, ShieldCheck } from 'lucide-react';
import { useState } from 'react';

const Navbar = () => {
    const { user, logout } = useAuth();
    const [isOpen, setIsOpen] = useState(false);
    const location = useLocation();

    const isRecruiter = (user && user.is_recruiter) || location.pathname.startsWith('/recruiter');
    const isCandidate = user && (user.is_candidate || (!user.is_recruiter && !location.pathname.startsWith('/recruiter')));

    const navLinks = user ? [
        ...(isRecruiter ? [
            { name: 'Dashboard', path: '/recruiter', icon: LayoutDashboard },
        ] : []),
        ...(isCandidate ? [
            { name: 'Jobs', path: '/candidate', icon: Briefcase },
            { name: 'AI Recommendations', path: '/recommendations', icon: Sparkles },
            { name: 'Auto-Apply Co-Pilot', path: '/auto-apply', icon: ShieldCheck },
        ] : []),
        { name: 'Profile', path: '/profile', icon: User },
    ] : [
        { name: 'Home', path: '/', icon: LayoutDashboard },
        { name: 'Sign In', path: '/login', icon: User },
    ];

    return (
        <nav className="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-md border-b border-slate-100/50">
            <div className="w-full max-w-[1720px] mx-auto px-6 sm:px-8 lg:px-10 xl:px-12">
                <div className="flex justify-between h-20">
                    <div className="flex items-center">
                        <Link to={user ? (isRecruiter ? '/recruiter' : '/candidate') : '/'} className="flex items-center gap-2.5 group">
                            <img 
                                src="/images/career-connect-logo.png" 
                                alt="Career Connect" 
                                className="w-10 h-10 object-contain group-hover:scale-105 transition-transform duration-200"
                            />
                            <span className="text-xl sm:text-2xl font-black tracking-tight text-slate-900">
                                Career<span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-600 to-blue-600">Connect</span>
                            </span>
                        </Link>
                    </div>

                    <div className="hidden md:flex items-center gap-6 lg:gap-8">
                        {!user && (
                            <Link to="/" className="text-sm font-semibold text-slate-700 transition-colors hover:text-cyan-600">
                                Home
                            </Link>
                        )}

                        {user ? (
                            <>
                                {isCandidate && (
                                    <>
                                        <Link to="/candidate" className="text-sm font-semibold text-slate-700 transition-colors hover:text-cyan-600">
                                            Jobs
                                        </Link>
                                        <Link
                                            to="/recommendations"
                                            className="text-sm font-bold text-cyan-700 hover:text-cyan-800 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-cyan-50 border border-cyan-200 transition-all shadow-sm hover:shadow"
                                        >
                                            <Sparkles className="w-4 h-4 text-cyan-600" />
                                            AI Recommendations
                                        </Link>
                                        <Link
                                            to="/auto-apply"
                                            className="text-sm font-bold text-indigo-700 hover:text-indigo-800 flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-indigo-50 border border-indigo-200 transition-all shadow-sm hover:shadow"
                                        >
                                            <ShieldCheck className="w-4 h-4 text-indigo-600" />
                                            Auto-Apply Co-Pilot
                                        </Link>
                                    </>
                                )}
                                {isRecruiter && (
                                    <Link
                                        to="/recruiter"
                                        className="text-sm font-semibold text-slate-700 transition-colors hover:text-cyan-600"
                                    >
                                        Dashboard
                                    </Link>
                                )}
                                <Link
                                    to="/profile"
                                    className="text-sm font-semibold text-slate-700 transition-colors hover:text-cyan-600"
                                >
                                    Profile
                                </Link>
                                <button
                                    onClick={logout}
                                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold text-slate-600 hover:text-red-600 transition-colors"
                                >
                                    <LogOut className="w-4 h-4" />
                                    Log out
                                </button>
                            </>
                        ) : (
                            <Link
                                to="/login"
                                className="bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold px-6 py-2.5 rounded-full shadow-sm hover:shadow transition-all"
                            >
                                Sign In
                            </Link>
                        )}
                    </div>

                    <div className="md:hidden flex items-center">
                        <button
                            onClick={() => setIsOpen(!isOpen)}
                            className="p-2 rounded-xl text-slate-500 hover:bg-slate-50 transition-colors"
                        >
                            {isOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
                        </button>
                    </div>
                </div>
            </div>

            {isOpen && (
                <div className="md:hidden bg-white border-b border-slate-100 animate-in fade-in slide-in-from-top-4 duration-300">
                    <div className="px-4 pt-2 pb-6 space-y-2">
                        {navLinks.map((link) => (
                            <Link
                                key={link.path}
                                to={link.path}
                                onClick={() => setIsOpen(false)}
                                className="flex items-center gap-3 px-4 py-3 rounded-xl text-base font-semibold text-slate-700 hover:bg-blue-50 hover:text-blue-600 transition-all"
                            >
                                {link.icon && <link.icon className="w-5 h-5" />}
                                {link.name}
                            </Link>
                        ))}
                        {user && (
                            <button
                                onClick={() => { logout(); setIsOpen(false); }}
                                className="flex items-center gap-3 w-full px-4 py-3 rounded-xl text-base font-semibold text-red-600 hover:bg-red-50 transition-all"
                            >
                                <LogOut className="w-5 h-5" />
                                Log out
                            </button>
                        )}
                    </div>
                </div>
            )}
        </nav>
    );
};

export default Navbar;
