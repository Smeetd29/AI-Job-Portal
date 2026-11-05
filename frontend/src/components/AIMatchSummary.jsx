import { Sparkles, CheckCircle2, AlertCircle, Briefcase, GraduationCap, RefreshCw, HelpCircle, Award } from 'lucide-react';

const AIMatchSummary = ({ aiSummary, generatedAt, onRegenerate, isRegenerating }) => {
    if (!aiSummary) return null;

    const score = aiSummary.match_score ?? 0;
    const badge = score >= 75 ? { text: 'Strong Match', color: 'text-emerald-700 bg-emerald-50 border-emerald-200' }
        : score >= 50 ? { text: 'Moderate Match', color: 'text-amber-700 bg-amber-50 border-amber-200' }
        : { text: 'Low Match', color: 'text-rose-700 bg-rose-50 border-rose-200' };

    const keySkills = (aiSummary.key_skills || []).slice(0, 12);
    const strongMatches = (aiSummary.matching_points || []).slice(0, 7);
    const gaps = (aiSummary.gaps || []).slice(0, 5);
    const educationSummary = aiSummary.education_summary || 'Educational background listed in resume.';
    const experienceSummary = aiSummary.experience_highlights?.[0] || 'Hands-on project and technical coursework experience.';

    return (
        <div className="bg-white rounded-2xl border border-indigo-100 shadow-sm overflow-hidden p-6 space-y-5">
            <div className="flex items-center justify-between flex-wrap gap-4 border-b border-gray-100 pb-4">
                <div className="flex items-center gap-2.5">
                    <div className="p-2 bg-indigo-50 text-indigo-600 rounded-xl"><Sparkles className="w-5 h-5" /></div>
                    <div>
                        <h4 className="text-base font-bold text-gray-900">AI Match Overview</h4>
                        <p className="text-xs text-gray-500">Recruiter quick summary</p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <div className={`px-3.5 py-1 rounded-full text-xs font-bold border flex items-center gap-1.5 ${badge.color}`}>
                        <Award className="w-3.5 h-3.5" />
                        <span>Match Score: {score}/100 ({badge.text})</span>
                    </div>
                    {onRegenerate && (
                        <button onClick={onRegenerate} disabled={isRegenerating} title="Regenerate" className="p-1.5 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg">
                            <RefreshCw className={`w-4 h-4 ${isRegenerating ? 'animate-spin text-indigo-600' : ''}`} />
                        </button>
                    )}
                </div>
            </div>

            {aiSummary.candidate_summary && (
                <div className="text-sm text-gray-700 bg-gray-50/70 p-3.5 rounded-xl border border-gray-100">
                    <span className="font-semibold text-gray-900">Summary: </span>{aiSummary.candidate_summary}
                </div>
            )}

            {keySkills.length > 0 && (
                <div className="space-y-2">
                    <div className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center gap-1.5">
                        <Briefcase className="w-3.5 h-3.5 text-indigo-500" /> Key Skills ({keySkills.length})
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                        {keySkills.map((s, i) => (
                            <span key={i} className="px-2.5 py-1 bg-slate-100 text-slate-800 rounded-md text-xs font-medium">{s}</span>
                        ))}
                    </div>
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-slate-50/70 rounded-xl p-3.5 border border-slate-100">
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1"><Briefcase className="w-3.5 h-3.5 text-slate-600" /> Experience Overview</p>
                    <p className="text-xs text-slate-700 leading-normal">{experienceSummary}</p>
                </div>
                <div className="bg-slate-50/70 rounded-xl p-3.5 border border-slate-100">
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1"><GraduationCap className="w-3.5 h-3.5 text-slate-600" /> Education</p>
                    <p className="text-xs text-slate-700 leading-normal">{educationSummary}</p>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-emerald-50/40 rounded-xl p-4 border border-emerald-100 space-y-2">
                    <p className="text-xs font-bold text-emerald-800 uppercase tracking-wider flex items-center gap-1.5"><CheckCircle2 className="w-4 h-4 text-emerald-600" /> Strong Matches ({strongMatches.length})</p>
                    <ul className="space-y-1.5 text-xs text-gray-800">
                        {strongMatches.map((m, i) => <li key={i} className="flex items-start gap-1.5"><span className="text-emerald-600 font-bold">•</span><span>{m.point}</span></li>)}
                    </ul>
                </div>
                <div className="bg-rose-50/30 rounded-xl p-4 border border-rose-100 space-y-2">
                    <p className="text-xs font-bold text-rose-800 uppercase tracking-wider flex items-center gap-1.5"><AlertCircle className="w-4 h-4 text-rose-500" /> Requirements Gaps ({gaps.length})</p>
                    {gaps.length > 0 ? (
                        <ul className="space-y-1.5 text-xs text-gray-800">
                            {gaps.map((g, i) => <li key={i} className="flex items-start gap-1.5"><span className="text-rose-500 font-bold">•</span><span>{g.point}</span></li>)}
                        </ul>
                    ) : <p className="text-xs text-emerald-700 font-medium py-1">✓ No major skill or qualification gaps identified.</p>}
                </div>
            </div>

            <div className="bg-indigo-50/70 border border-indigo-100 rounded-xl p-4">
                <p className="text-xs font-bold text-indigo-900 uppercase tracking-wider flex items-center gap-1.5 mb-1"><HelpCircle className="w-3.5 h-3.5 text-indigo-600" /> Why this match?</p>
                <p className="text-xs text-indigo-950 leading-relaxed font-medium">{aiSummary.recommendation || 'Candidate demonstrates solid alignment with core required skills.'}</p>
            </div>

            {generatedAt && <div className="text-[11px] text-gray-400 text-right">Generated {new Date(generatedAt).toLocaleString()}</div>}
        </div>
    );
};

export default AIMatchSummary;
