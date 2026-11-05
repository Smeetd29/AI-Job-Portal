import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { LogIn, UserPlus, Loader2, AlertCircle, User, Briefcase, Mail, Lock, Sparkles, ShieldCheck, Check } from 'lucide-react';
import AuthBrandingPanel from '../../components/auth/AuthBrandingPanel';
import AuthInput from '../../components/auth/AuthInput';

export default function AuthPage({ mode = 'login' }) {
    const isSignup = mode === 'signup';
    const [formData, setFormData] = useState({ username: '', email: '', password: '', role: 'candidate' });
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const { login, signup, user, loading: authLoading } = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
        if (!isSignup && !authLoading && user) {
            navigate(user.is_recruiter ? '/recruiter' : '/candidate', { replace: true });
        }
    }, [user, navigate, isSignup, authLoading]);

    const handleChange = (e) => setFormData({ ...formData, [e.target.name || e.target.id]: e.target.value });

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);
        try {
            if (isSignup) {
                await signup({ ...formData, is_candidate: formData.role === 'candidate', is_recruiter: formData.role === 'recruiter' });
                navigate('/login');
            } else {
                const ok = await login(formData.username, formData.password);
                if (!ok) setError('Sign in failed. Please check your credentials.');
            }
        } catch (err) {
            setError(err.response?.data?.error || err.response?.data?.detail || (err.response?.data ? Object.values(err.response.data).flat().join(', ') : 'Action failed. Please try again.'));
        } finally {
            setIsLoading(false);
        }
    };

    const fillDemo = (u, p) => { setFormData({ ...formData, username: u, password: p }); setError(''); };

    return (
        <div className="w-full flex-1 min-h-[calc(100vh-140px)] py-4 sm:py-8 px-4 flex items-center justify-center bg-slate-50/50">
            <div className="max-w-4xl xl:max-w-5xl w-full rounded-3xl shadow-xl border border-slate-200/80 bg-white overflow-hidden grid grid-cols-1 lg:grid-cols-12">
                <div className="lg:col-span-5 h-full">
                    <AuthBrandingPanel mode={mode} />
                </div>
                <div className="lg:col-span-7 p-6 sm:p-8 lg:p-10 flex flex-col justify-center bg-white relative">
                    <div>
                        <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold tracking-wide uppercase mb-2 ${isSignup ? 'bg-cyan-50 border border-cyan-100 text-cyan-700' : 'bg-blue-50 border border-blue-100 text-blue-700'}`}>
                            <Sparkles className="w-3.5 h-3.5" />
                            {isSignup ? 'Join in 60 Seconds' : 'Welcome Back'}
                        </div>
                        <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
                            {isSignup ? 'Create your account' : 'Sign in to your account'}
                        </h1>
                        <p className="mt-1 text-xs sm:text-sm text-slate-500">
                            {isSignup ? 'Start matching with top companies and hiring managers today.' : 'Access your AI matches, direct interviews, and applications.'}
                        </p>
                    </div>

                    {!isSignup && (
                        <div className="mt-4 p-3 rounded-2xl bg-slate-50 border border-slate-200/80">
                            <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-2 flex items-center justify-between">
                                <span>Quick Demo Logins</span>
                                <span className="text-[10px] font-medium text-blue-600 lowercase bg-blue-50 px-2 py-0.5 rounded-md">1-click test</span>
                            </p>
                            <div className="grid grid-cols-2 gap-2">
                                <button type="button" onClick={() => fillDemo('Smeet', '12345678')} className="flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-white hover:bg-cyan-50 border border-slate-200 hover:border-cyan-300 text-xs font-semibold text-slate-700 transition-all shadow-sm cursor-pointer">
                                    <User className="w-3.5 h-3.5 text-cyan-600" />
                                    <span>Candidate (Smeet)</span>
                                </button>
                                <button type="button" onClick={() => fillDemo('Jeet', '12345678')} className="flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-white hover:bg-blue-50 border border-slate-200 hover:border-blue-300 text-xs font-semibold text-slate-700 transition-all shadow-sm cursor-pointer">
                                    <Briefcase className="w-3.5 h-3.5 text-blue-600" />
                                    <span>Recruiter (Jeet)</span>
                                </button>
                            </div>
                        </div>
                    )}

                    {isSignup && (
                        <div className="mt-3">
                            <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">I want to join as:</p>
                            <div className="grid grid-cols-2 gap-2">
                                {[['candidate', 'Job Seeker', 'Find dream jobs', User, 'blue'], ['recruiter', 'Recruiter', 'Hire top talent', Briefcase, 'indigo']].map(([r, title, sub, Icon, col]) => (
                                    <button key={r} type="button" onClick={() => setFormData({ ...formData, role: r })} className={`flex items-start gap-2 p-2.5 rounded-xl border-2 text-left transition-all cursor-pointer ${formData.role === r ? `border-${col}-600 bg-${col}-50/70 shadow-sm ring-1 ring-${col}-600/30` : 'border-slate-200 bg-slate-50/50 hover:bg-slate-50'}`}>
                                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${formData.role === r ? `bg-${col}-600 text-white shadow-sm` : 'bg-white border border-slate-200 text-slate-500'}`}>
                                            <Icon className="w-3.5 h-3.5" />
                                        </div>
                                        <div className="min-w-0 flex-1">
                                            <div className="flex items-center justify-between">
                                                <p className={`text-xs font-bold ${formData.role === r ? `text-${col}-950` : 'text-slate-800'}`}>{title}</p>
                                                {formData.role === r && <Check className="w-3 h-3 text-white rounded-full bg-blue-600 p-0.5" />}
                                            </div>
                                            <p className="text-[10px] text-slate-500 truncate">{sub}</p>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {error && (
                        <div className="mt-3 bg-rose-50 border border-rose-200 p-2.5 rounded-xl flex items-start gap-2.5 text-rose-700">
                            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-rose-600" />
                            <p className="text-xs font-medium">{error}</p>
                        </div>
                    )}

                    <form className="mt-3 space-y-2.5" onSubmit={handleSubmit}>
                        <AuthInput id="username" name="username" label="Username" required compact={isSignup} value={formData.username} onChange={handleChange} disabled={isLoading} placeholder={isSignup ? "Choose a unique username" : "e.g. Smeet or Jeet"} icon={User} autoComplete="username" />
                        {isSignup && (
                            <AuthInput id="email" name="email" type="email" label="Email Address" required compact={true} value={formData.email} onChange={handleChange} disabled={isLoading} placeholder="you@example.com" icon={Mail} autoComplete="email" />
                        )}
                        <AuthInput id="password" name="password" label="Password" type="password" required compact={isSignup} value={formData.password} onChange={handleChange} disabled={isLoading} placeholder={isSignup ? "Minimum 8 characters" : "••••••••"} icon={Lock} autoComplete={isSignup ? "new-password" : "current-password"} />

                        <div className="pt-1">
                            <button type="submit" disabled={isLoading} className="w-full h-11 bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-500 hover:from-blue-700 hover:to-cyan-600 text-white font-bold rounded-xl shadow-lg shadow-blue-500/25 transition-all flex items-center justify-center gap-2 text-sm disabled:opacity-60 cursor-pointer">
                                {isLoading ? (
                                    <>
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        <span>{isSignup ? 'Creating account...' : 'Authenticating...'}</span>
                                    </>
                                ) : (
                                    <>
                                        {isSignup ? <UserPlus className="w-4 h-4" /> : <LogIn className="w-4 h-4" />}
                                        <span>{isSignup ? 'Create My Career Account' : 'Sign in to Dashboard'}</span>
                                    </>
                                )}
                            </button>
                        </div>

                        <div className="text-center pt-1">
                            <p className="text-xs text-slate-500">
                                {isSignup ? 'Already have an account? ' : "Don't have an account? "}
                                <Link to={isSignup ? '/login' : '/signup'} className="font-bold text-blue-600 hover:text-cyan-600 transition-colors">
                                    {isSignup ? 'Sign in' : 'Create an account'}
                                </Link>
                            </p>
                        </div>

                        <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-center gap-2 text-slate-400 text-[11px]">
                            <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                            <span>{isSignup ? 'Instant Access • No Credit Card Required' : '256-Bit SSL Encrypted • Direct Recruiter Connect'}</span>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
}
