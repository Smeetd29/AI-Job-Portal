import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import api from '../../axios';
import { Sparkles, Sliders, RefreshCw, AlertCircle, FileText, SearchX, MapPin, Briefcase, ChevronRight } from 'lucide-react';

const RecommendationJobCard = ({ job }) => {
    const [insights, setInsights] = useState(null);
    const [insightsLoading, setInsightsLoading] = useState(false);
    const [insightsError, setInsightsError] = useState('');

    const loadInsights = async () => {
        setInsightsLoading(true);
        setInsightsError('');
        try {
            const response = await api.post('/api/profile/insights/', { job_id: job.job_id });
            setInsights(response.data.insights.job_specific);
        } catch (error) {
            setInsightsError(error.response?.data?.detail || 'Unable to generate job insights.');
        } finally {
            setInsightsLoading(false);
        }
    };

    return (
    <div className="group bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm hover:shadow-md transition-all">
        <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
                <Link to={`/jobs/${job.job_id}`}>
                    <h3 className="text-lg font-bold text-slate-900 group-hover:text-cyan-600 truncate">{job.title}</h3>
                </Link>
                <p className="text-slate-600 text-sm mt-0.5">{job.company}</p>
                <div className="flex flex-wrap items-center gap-2 mt-2 text-xs text-slate-500">
                    <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" />{job.location || 'Onsite'}</span>
                    <span>•</span>
                    <span className="flex items-center gap-1"><Briefcase className="w-3.5 h-3.5" />{job.job_type || 'Full Time'}</span>
                    {job.pay_amount && <><span>•</span><span className="font-semibold text-emerald-600">₹{Number(job.pay_amount).toLocaleString()}</span></>}
                </div>
                {job.matched_skills && job.matched_skills.length > 0 && (
                    <div className="mt-3 flex flex-wrap items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-slate-400 mr-1">Matched Skills:</span>
                        {job.matched_skills.map((skill, idx) => (
                            <span key={idx} className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200/60">
                                {skill}
                            </span>
                        ))}
                    </div>
                )}
            </div>
            <div className="text-right px-4 py-2 rounded-2xl border bg-cyan-50 border-cyan-200 text-cyan-700">
                <div className="text-2xl font-black">{job.match_score}%</div>
                <div className="text-[10px] font-bold uppercase">Match</div>
            </div>
        </div>
        <div className="mt-4 flex items-center justify-between pt-3 border-t border-slate-100">
            <span className="text-xs text-slate-400">Based on your resume and skill profile</span>
            <div className="flex items-center gap-2">
                <button
                    type="button"
                    onClick={loadInsights}
                    disabled={insightsLoading}
                    className="px-3 py-1.5 rounded-xl text-xs font-bold text-cyan-800 bg-cyan-50 hover:bg-cyan-100 disabled:opacity-50"
                >
                    {insightsLoading ? 'Analyzing…' : 'Why this role?'}
                </button>
                <Link to={`/jobs/${job.job_id}`} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-bold text-white bg-slate-900 hover:bg-cyan-600">
                    View Job <ChevronRight className="w-3.5 h-3.5" />
                </Link>
            </div>
        </div>
        {insightsError && <p role="alert" className="mt-3 text-xs text-rose-700">{insightsError}</p>}
        {insights && (
            <div className="mt-4 rounded-xl border border-cyan-100 bg-cyan-50/60 p-4 space-y-3">
                <p className="text-sm text-slate-800">{insights.overall_assessment}</p>
                {insights.matching_strengths?.length > 0 && (
                    <div>
                        <h4 className="text-xs font-bold uppercase text-emerald-800">Resume evidence matching the role</h4>
                        <ul className="mt-1 space-y-1 text-xs text-slate-700">
                            {insights.matching_strengths.map((match, index) => (
                                <li key={`${match.skill}-${index}`}>{match.skill}: “{match.resume_evidence}”</li>
                            ))}
                        </ul>
                    </div>
                )}
                {insights.gaps?.length > 0 && (
                    <div>
                        <h4 className="text-xs font-bold uppercase text-amber-800">Not demonstrated in the supplied resume</h4>
                        <ul className="mt-1 space-y-1 text-xs text-slate-700">
                            {insights.gaps.map((gap, index) => <li key={`${gap.requirement}-${index}`}>{gap.requirement} — this does not establish that you lack the skill.</li>)}
                        </ul>
                    </div>
                )}
                {insights.improvement_actions?.length > 0 && (
                    <ul className="list-disc pl-5 text-xs text-slate-700">
                        {insights.improvement_actions.map((action, index) => <li key={index}>{action}</li>)}
                    </ul>
                )}
            </div>
        )}
    </div>
    );
};

const RecommendationsPage = () => {
    const [sliderValue, setSliderValue] = useState(50);
    const [recommendations, setRecommendations] = useState([]);
    const [totalEligible, setTotalEligible] = useState(0);
    const [appliedCount, setAppliedCount] = useState(0);
    const [hasResume, setHasResume] = useState(true);
    const [resumeMessage, setResumeMessage] = useState('');
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState(null);

    const fetchRecommendations = useCallback(async (minMatch, forceRefresh = false) => {
        if (forceRefresh) setRefreshing(true);
        else setLoading(true);
        setError(null);

        try {
            const params = new URLSearchParams({
                min_match: minMatch.toString(),
            });
            if (forceRefresh) params.append('refresh', 'true');

            const res = await api.get(`/api/ai/recommendations/?${params.toString()}`);
            const data = res.data;

            if (data.has_resume === false) {
                setHasResume(false);
                setResumeMessage(data.message || 'Upload a resume to receive AI job recommendations.');
                setRecommendations([]);
                setTotalEligible(0);
                setAppliedCount(0);
            } else {
                setHasResume(true);
                setRecommendations(data.results || []);
                setTotalEligible(data.total_eligible || 0);
                setAppliedCount(data.applied_count || 0);
            }
        } catch (err) {
            console.error('Failed to load recommendations', err);
            const detail = err.response?.data?.detail || 'Unable to fetch recommendations right now.';
            setError(detail);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, []);

    useEffect(() => {
        const timer = setTimeout(() => {
            fetchRecommendations(sliderValue);
        }, 200);
        return () => clearTimeout(timer);
    }, [sliderValue, fetchRecommendations]);

    const handleRefresh = () => {
        fetchRecommendations(sliderValue, true);
    };

    return (
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
                <div>
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-cyan-50 text-cyan-700 border border-cyan-200/60 mb-2">
                        <Sparkles className="w-3.5 h-3.5 text-cyan-600 animate-pulse" />
                        AI-Powered Career Matcher
                    </div>
                    <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
                        AI Job Recommendations
                    </h1>
                    <p className="text-slate-600 text-sm mt-1">
                        Jobs recommended for you based on your resume and skills.
                    </p>
                </div>

                {hasResume && (
                    <button
                        onClick={handleRefresh}
                        disabled={refreshing || loading}
                        className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-xl bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 hover:text-cyan-600 transition-all shadow-sm disabled:opacity-50"
                    >
                        <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-cyan-600' : ''}`} />
                        {refreshing ? 'Re-scoring...' : 'Refresh Matches'}
                    </button>
                )}
            </div>

            {error && (
                <div className="mt-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 flex items-center gap-3 text-sm">
                    <AlertCircle className="w-5 h-5 shrink-0" />
                    <span>{error}</span>
                </div>
            )}

            {!hasResume && !loading ? (
                <div className="mt-10 max-w-lg mx-auto bg-white rounded-3xl border border-slate-200/80 p-8 sm:p-10 text-center shadow-sm">
                    <div className="w-16 h-16 rounded-2xl bg-cyan-50 border border-cyan-200 text-cyan-600 flex items-center justify-center mx-auto mb-4">
                        <FileText className="w-8 h-8" />
                    </div>
                    <h2 className="text-xl font-bold text-slate-900">Upload Resume to Get Recommendations</h2>
                    <p className="text-slate-600 text-sm mt-2 leading-relaxed">
                        {resumeMessage || 'Upload your resume to your profile so our AI matching engine can score available jobs against your skills and experience.'}
                    </p>
                    <Link
                        to="/profile"
                        className="mt-6 inline-flex items-center justify-center px-6 py-3 rounded-xl bg-cyan-600 hover:bg-cyan-700 text-white text-sm font-bold shadow-sm hover:shadow transition-all"
                    >
                        Go to Profile & Upload Resume
                    </Link>
                </div>
            ) : (
                <>
                    <div className="mt-6 bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
                            <div className="flex items-center gap-2.5">
                                <div className="p-2 rounded-xl bg-cyan-50 text-cyan-600">
                                    <Sliders className="w-5 h-5" />
                                </div>
                                <div>
                                    <h2 className="text-base font-bold text-slate-900">Minimum Match Threshold</h2>
                                    <p className="text-xs text-slate-500">
                                        Show jobs with <span className="font-semibold text-cyan-700">{sliderValue}%+</span> match
                                    </p>
                                </div>
                            </div>

                            <div className="flex items-center gap-3">
                                <span className="text-xs text-slate-400 font-semibold uppercase">Presets:</span>
                                {[0, 50, 70, 85].map((preset) => (
                                    <button
                                        key={preset}
                                        onClick={() => setSliderValue(preset)}
                                        className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${sliderValue === preset
                                            ? 'bg-cyan-600 text-white shadow-sm'
                                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                            }`}
                                    >
                                        {preset === 0 ? 'All (0%)' : `${preset}%+`}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="mt-5">
                            <div className="flex items-center justify-between text-xs font-bold text-slate-500 mb-2">
                                <span>0%</span>
                                <span className="text-sm sm:text-base font-black text-cyan-600 bg-cyan-50 px-3 py-0.5 rounded-full border border-cyan-200">
                                    {sliderValue}% Match
                                </span>
                                <span>100%</span>
                            </div>
                            <input
                                type="range"
                                min="0"
                                max="100"
                                step="1"
                                value={sliderValue}
                                onChange={(e) => setSliderValue(Number(e.target.value))}
                                className="w-full h-2.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-cyan-600"
                            />
                        </div>

                        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 pt-3 border-t border-slate-100">
                            <span>
                                Found <strong className="text-slate-900 font-bold">{recommendations.length}</strong> matching jobs
                                {totalEligible > 0 && ` out of ${totalEligible} open jobs`}
                                {appliedCount > 0 && (
                                    <span className="ml-2 text-slate-400">
                                        ({appliedCount} applied jobs excluded)
                                    </span>
                                )}
                            </span>
                            <span className="text-slate-400">
                                Ranked by AI Match Score
                            </span>
                        </div>
                    </div>

                    <div className="mt-6 space-y-4">
                        {loading && recommendations.length === 0 ? (
                            <div className="py-16 text-center">
                                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-600 mb-3" />
                                <p className="text-slate-500 text-sm font-medium">
                                    Evaluating available jobs with AI Matching Pipeline...
                                </p>
                            </div>
                        ) : recommendations.length === 0 ? (
                            <div className="bg-white rounded-2xl border border-slate-200/80 p-10 text-center shadow-sm">
                                <div className="w-12 h-12 rounded-xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center mx-auto mb-3">
                                    <SearchX className="w-6 h-6" />
                                </div>
                                <h3 className="text-lg font-bold text-slate-900">No jobs match your current threshold ({sliderValue}%+)</h3>
                                <p className="text-slate-600 text-sm mt-1 max-w-md mx-auto">
                                    Try lowering the minimum match percentage slider to discover more jobs that align with your background.
                                </p>
                                <button
                                    onClick={() => setSliderValue(40)}
                                    className="mt-4 px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-sm font-bold transition-colors"
                                >
                                    Lower Threshold to 40%
                                </button>
                            </div>
                        ) : (
                            recommendations.map((job) => (
                                <RecommendationJobCard key={job.job_id} job={job} />
                            ))
                        )}
                    </div>
                </>
            )}
        </div>
    );
};

export default RecommendationsPage;
