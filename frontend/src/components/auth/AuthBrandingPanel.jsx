import { Sparkles, CheckCircle2, Star } from 'lucide-react';

const AuthBrandingPanel = ({ mode = 'login' }) => {
    const isSignup = mode === 'signup';
    return (
        <div className="bg-gradient-to-br from-blue-600 via-sky-600 to-indigo-700 p-6 sm:p-8 flex flex-col justify-between text-white relative overflow-hidden h-full">
            <div className="relative z-10 space-y-4">
                <div className="flex items-center gap-2.5">
                    <img src="/images/career-connect-logo.png" alt="Career Connect" className="h-8 w-auto object-contain brightness-105" />
                    <div>
                        <span className="text-xl font-black tracking-tight text-white leading-none">Career<span className="text-cyan-200">Connect</span></span>
                        <span className="block text-[10px] font-semibold text-cyan-200/90 uppercase mt-0.5">AI-Powered Career Portal</span>
                    </div>
                </div>
                <div className="space-y-2">
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/15 border border-white/25 text-cyan-100 text-[11px] font-bold">
                        <Sparkles className="w-3 h-3 text-cyan-300" />
                        <span>{isSignup ? 'Start Your Free Journey' : 'Smart Career Intelligence'}</span>
                    </div>
                    <h2 className="text-xl sm:text-2xl font-black text-white leading-tight">
                        {isSignup ? 'Unlock your full career potential.' : 'Land your dream role 3x faster.'}
                    </h2>
                    <p className="text-xs text-cyan-100/90 leading-relaxed max-w-sm">
                        {isSignup ? 'Join over 50,000 top professionals matching directly with pre-screened recruiters through predictive AI.' : 'Match directly with verified tech employers using deep resume extraction and real-time skill alignment.'}
                    </p>
                </div>
            </div>

            <div className="my-6 relative z-10">
                <div className="grid grid-cols-3 gap-2.5 text-center">
                    {[['98%', 'Match Accuracy'], ['1-Click', 'AI Autofill'], ['1,200+', 'Recruiters']].map(([val, lbl]) => (
                        <div key={lbl} className="p-3 rounded-xl bg-white/10 border border-white/15 backdrop-blur-sm">
                            <p className="text-lg font-black text-white leading-tight">{val}</p>
                            <p className="text-[10px] font-semibold text-cyan-100 leading-tight mt-1">{lbl}</p>
                        </div>
                    ))}
                </div>
            </div>

            <div className="relative z-10 pt-3 border-t border-white/15 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="flex items-center gap-0.5 text-amber-300">
                        {[...Array(5)].map((_, i) => <Star key={i} className="w-2.5 h-2.5 fill-amber-300" />)}
                    </div>
                    <p className="text-[10px] text-white/90 font-medium">50,000+ careers accelerated</p>
                </div>
                <div className="flex items-center gap-1 px-2 py-0.5 rounded bg-white/10 border border-white/15 text-[10px] font-semibold text-cyan-100">
                    <CheckCircle2 className="w-3 h-3 text-emerald-300" /> Verified
                </div>
            </div>
        </div>
    );
};

export default AuthBrandingPanel;
