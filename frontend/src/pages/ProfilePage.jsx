import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import api from '../axios';
import {
    User, Mail, Shield, Save, Loader2, CheckCircle2, Upload,
    Building2, Briefcase, FileText, Sparkles, GraduationCap, Eye, AlertCircle
} from 'lucide-react';
import ResumePreviewModal from '../components/ResumePreviewModal';

const ProfilePage = () => {
    const { user, refreshUser } = useAuth();
    const [formData, setFormData] = useState({
        username: user?.username || '',
        email: user?.email || '',
    });
    const [profileData, setProfileData] = useState({});
    const [isSavingAccount, setIsSavingAccount] = useState(false);
    const [isSavingProfile, setIsSavingProfile] = useState(false);
    const [message, setMessage] = useState('');
    const [errorMsg, setErrorMsg] = useState('');
    const [isPreviewOpen, setIsPreviewOpen] = useState(false);
    const [resumeInsights, setResumeInsights] = useState(null);
    const [isGeneratingInsights, setIsGeneratingInsights] = useState(false);

    const isCandidate = user?.is_candidate;
    const isRecruiter = user?.is_recruiter;

    useEffect(() => {
        if (user) {
            setFormData({ username: user.username, email: user.email });
            fetchRoleProfile();
        }
    }, [user]);

    const fetchRoleProfile = () => {
        if (user?.is_candidate) {
            setProfileData(user.candidate_profile || {});
        } else {
            setProfileData(user.recruiter_profile || {});
        }
    };

    const handleUserUpdate = async (e) => {
        e.preventDefault();
        setIsSavingAccount(true);
        setMessage('');
        setErrorMsg('');
        try {
            await api.patch('/profile/', formData);
            setMessage('Account credentials updated successfully!');
            await refreshUser();
        } catch (err) {
            setErrorMsg(err.response?.data?.username?.[0] || err.response?.data?.email?.[0] || 'Failed to update credentials.');
        } finally {
            setIsSavingAccount(false);
            setTimeout(() => setMessage(''), 4000);
        }
    };

    const handleRoleUpdate = async (e) => {
        e.preventDefault();
        setIsSavingProfile(true);
        setMessage('');
        setErrorMsg('');
        try {
            const data = new FormData();
            Object.keys(profileData).forEach(key => {
                if (key !== 'resume' || (profileData[key] instanceof File)) {
                    data.append(key, profileData[key] || '');
                }
            });
            await api.post('/profile/resume/', data, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            setMessage(isCandidate ? 'Candidate profile and resume saved!' : 'Company details updated successfully!');
            setResumeInsights(null);
            await refreshUser();
        } catch (err) {
            setErrorMsg(err.response?.data?.detail || 'Failed to update profile details.');
        } finally {
            setIsSavingProfile(false);
            setTimeout(() => setMessage(''), 4000);
        }
    };

    const handleGenerateInsights = async () => {
        setIsGeneratingInsights(true);
        setErrorMsg('');
        try {
            const response = await api.post('/api/profile/insights/', {});
            setResumeInsights(response.data.insights);
        } catch (err) {
            setErrorMsg(err.response?.data?.detail || 'Unable to analyze this resume right now.');
        } finally {
            setIsGeneratingInsights(false);
        }
    };

    const resumeFileName = profileData.resume
        ? (typeof profileData.resume === 'string'
            ? (profileData.resume.split('/').pop() || 'Profile_Resume.pdf')
            : (profileData.resume.name || 'New_Resume.pdf'))
        : null;

    return (
        <div className="max-w-6xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-8 animate-fade-in">
            <div className={`rounded-3xl p-6 sm:p-8 text-white relative overflow-hidden shadow-xl ${isRecruiter
                ? 'bg-gradient-to-r from-slate-900 via-indigo-950 to-blue-900'
                : 'bg-gradient-to-r from-cyan-700 via-blue-700 to-indigo-800'
                }`}>
                <div className="relative z-10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
                    <div className="flex items-center gap-5">
                        <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-3xl font-black text-white shadow-inner">
                            {user?.username ? user.username.charAt(0).toUpperCase() : <User className="w-10 h-10" />}
                        </div>
                        <div>
                            <div className="flex items-center gap-3">
                                <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">{user?.username}</h1>
                                <span className="inline-flex items-center gap-1 px-3 py-0.5 rounded-full text-xs font-semibold bg-white/20 backdrop-blur-md border border-white/30 text-white">
                                    {isRecruiter ? <Building2 className="w-3.5 h-3.5" /> : <Sparkles className="w-3.5 h-3.5" />}
                                    {isRecruiter ? 'Recruiter' : 'Candidate'}
                                </span>
                            </div>
                            <p className="text-white/80 text-sm mt-1 flex items-center gap-2">
                                <Mail className="w-4 h-4 opacity-80" /> {user?.email || 'No email set'}
                            </p>
                        </div>
                    </div>

                    {message && (
                        <div className="flex items-center gap-2 bg-emerald-500/90 text-white px-4 py-2.5 rounded-xl border border-emerald-400 text-sm font-medium shadow-lg animate-slide-up backdrop-blur-md">
                            <CheckCircle2 className="w-4 h-4 shrink-0" />
                            <span>{message}</span>
                        </div>
                    )}
                    {errorMsg && (
                        <div className="flex items-center gap-2 bg-rose-500/90 text-white px-4 py-2.5 rounded-xl border border-rose-400 text-sm font-medium shadow-lg animate-slide-up backdrop-blur-md">
                            <AlertCircle className="w-4 h-4 shrink-0" />
                            <span>{errorMsg}</span>
                        </div>
                    )}
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="space-y-6">
                    <div className="card p-6 border border-slate-200/80 shadow-sm space-y-5 bg-white">
                        <h3 className="text-base font-bold text-slate-900 border-b border-slate-100 pb-3 flex items-center gap-2">
                            <Shield className="w-4 h-4 text-primary-600" />
                            Account Status
                        </h3>
                        <div className="space-y-3 text-sm">
                            <div className="flex items-center justify-between py-1">
                                <span className="text-slate-500">Account Type</span>
                                <span className="font-semibold text-slate-800">{isRecruiter ? 'Recruiter' : 'Candidate'}</span>
                            </div>
                            <div className="flex items-center justify-between py-1">
                                <span className="text-slate-500">Username</span>
                                <span className="font-medium text-slate-800">{user?.username}</span>
                            </div>
                            {isCandidate && (
                                <div className="flex items-center justify-between py-1">
                                    <span className="text-slate-500">Default Resume</span>
                                    {profileData.resume ? (
                                        <span className="inline-flex items-center gap-1 text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md text-xs font-semibold">
                                            <CheckCircle2 className="w-3 h-3" /> Uploaded
                                        </span>
                                    ) : (
                                        <span className="text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-md text-xs font-semibold">
                                            Missing
                                        </span>
                                    )}
                                </div>
                            )}
                            {isRecruiter && (
                                <div className="flex items-center justify-between py-1">
                                    <span className="text-slate-500">Company</span>
                                    <span className="font-medium text-slate-800 truncate max-w-[150px]">
                                        {profileData.company_name || 'Not configured'}
                                    </span>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="lg:col-span-2 space-y-8">
                    <form onSubmit={handleUserUpdate} className="card p-6 sm:p-7 border border-slate-200/80 shadow-sm bg-white space-y-5">
                        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                            <div>
                                <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                                    <User className="w-5 h-5 text-primary-600" />
                                    Account Credentials
                                </h3>
                                <p className="text-xs text-slate-500 mt-0.5">Manage your username and registered email address</p>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                            <div>
                                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                                    Username
                                </label>
                                <input
                                    type="text"
                                    value={formData.username}
                                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                    className="w-full px-4 py-2.5 rounded-xl border border-slate-300 focus:ring-2 focus:ring-primary-500/20 focus:border-primary-600 outline-none text-sm transition-all"
                                    required
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                                    Email Address
                                </label>
                                <input
                                    type="email"
                                    value={formData.email}
                                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                    className="w-full px-4 py-2.5 rounded-xl border border-slate-300 focus:ring-2 focus:ring-primary-500/20 focus:border-primary-600 outline-none text-sm transition-all"
                                    required
                                />
                            </div>
                        </div>

                        <div className="pt-2 flex justify-end">
                            <button
                                type="submit"
                                disabled={isSavingAccount}
                                className="btn btn-primary px-5 py-2.5 text-sm font-semibold flex items-center gap-2 rounded-xl shadow-sm hover:shadow"
                            >
                                {isSavingAccount ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                                Save Credentials
                            </button>
                        </div>
                    </form>

                    <form onSubmit={handleRoleUpdate} className="card p-6 sm:p-7 border border-slate-200/80 shadow-sm bg-white space-y-6">
                        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                            <div>
                                <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                                    {isCandidate ? <Sparkles className="w-5 h-5 text-cyan-600" /> : <Building2 className="w-5 h-5 text-blue-600" />}
                                    {isCandidate ? 'Candidate Profile & Resume' : 'Company & Recruiter Details'}
                                </h3>
                                <p className="text-xs text-slate-500 mt-0.5">
                                    {isCandidate
                                        ? 'Your default resume and skills used for 1-click job applications and AI recommendations'
                                        : 'Company profile shown to candidates on your job postings'}
                                </p>
                            </div>
                        </div>

                        {isCandidate ? (
                            <div className="space-y-6">
                                <div>
                                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                                        Default Profile Resume (PDF, DOC, DOCX)
                                    </label>

                                    {resumeFileName ? (
                                        <div className="bg-emerald-50/70 border border-emerald-200 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                                            <div className="flex items-center gap-3 min-w-0">
                                                <div className="w-10 h-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center shrink-0 shadow-sm">
                                                    <FileText className="w-5 h-5" />
                                                </div>
                                                <div className="min-w-0">
                                                    <div className="flex items-center gap-2">
                                                        <p className="font-semibold text-sm text-slate-900 truncate">{resumeFileName}</p>
                                                        <span className="shrink-0 text-[10px] font-bold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full">
                                                            Active Default
                                                        </span>
                                                    </div>
                                                    <p className="text-xs text-slate-500 mt-0.5">Automatically attached to 1-click applications</p>
                                                </div>
                                            </div>

                                            <div className="flex items-center gap-2 shrink-0">
                                                <button
                                                    type="button"
                                                    onClick={() => setIsPreviewOpen(true)}
                                                    className="px-3 py-1.5 rounded-lg border border-emerald-300 text-emerald-800 hover:bg-emerald-100 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                                                >
                                                    <Eye className="w-3.5 h-3.5" /> Preview
                                                </button>
                                                <label className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-sm">
                                                    <Upload className="w-3.5 h-3.5" /> Replace
                                                    <input
                                                        type="file"
                                                        className="hidden"
                                                        accept=".pdf,.doc,.docx"
                                                        onChange={(e) => {
                                                            setProfileData({ ...profileData, resume: e.target.files[0] });
                                                            setResumeInsights(null);
                                                        }}
                                                    />
                                                </label>
                                            </div>
                                        </div>
                                    ) : (
                                        <label className="border-2 border-dashed border-slate-300 hover:border-cyan-500 hover:bg-cyan-50/40 rounded-2xl p-6 flex flex-col items-center justify-center cursor-pointer transition-all duration-200 group">
                                            <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 group-hover:bg-cyan-100 group-hover:text-cyan-600 flex items-center justify-center mb-2 transition-colors">
                                                <Upload className="w-6 h-6" />
                                            </div>
                                            <p className="text-sm font-semibold text-slate-700 group-hover:text-cyan-800">
                                                Click to upload your default resume
                                            </p>
                                            <p className="text-xs text-slate-400 mt-0.5">PDF, DOC, DOCX up to 10MB</p>
                                            <input
                                                type="file"
                                                className="hidden"
                                                accept=".pdf,.doc,.docx"
                                                onChange={(e) => {
                                                    setProfileData({ ...profileData, resume: e.target.files[0] });
                                                    setResumeInsights(null);
                                                }}
                                            />
                                        </label>
                                    )}
                                </div>

                                <div>
                                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                        <Briefcase className="w-3.5 h-3.5 text-primary-600" />
                                        Skills & Core Competencies
                                    </label>
                                    <textarea
                                        value={profileData.skills || ''}
                                        onChange={(e) => setProfileData({ ...profileData, skills: e.target.value })}
                                        placeholder="e.g. Python, React, Django, PostgreSQL, Docker, AWS"
                                        rows={3}
                                        className="w-full px-4 py-2.5 rounded-xl border border-slate-300 focus:ring-2 focus:ring-primary-500/20 focus:border-primary-600 outline-none text-sm transition-all"
                                    />
                                    <p className="text-[11px] text-slate-400 mt-1">Separate skills with commas</p>
                                </div>

                                <div>
                                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                        <GraduationCap className="w-3.5 h-3.5 text-primary-600" />
                                        Education & Degrees
                                    </label>
                                    <textarea
                                        value={profileData.education || ''}
                                        onChange={(e) => setProfileData({ ...profileData, education: e.target.value })}
                                        placeholder="e.g. B.Tech Computer Science - Stanford University (2024)"
                                        rows={3}
                                        className="w-full px-4 py-2.5 rounded-xl border border-slate-300 focus:ring-2 focus:ring-primary-500/20 focus:border-primary-600 outline-none text-sm transition-all"
                                    />
                                </div>
                            </div>
                        ) : (
                            <div className="space-y-6">
                                <div>
                                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                        <Building2 className="w-3.5 h-3.5 text-blue-600" />
                                        Company Name
                                    </label>
                                    <input
                                        type="text"
                                        value={profileData.company_name || ''}
                                        onChange={(e) => setProfileData({ ...profileData, company_name: e.target.value })}
                                        placeholder="e.g. Acme Innovations Inc."
                                        className="w-full px-4 py-2.5 rounded-xl border border-slate-300 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 outline-none text-sm transition-all"
                                    />
                                </div>

                                <div>
                                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                                        Company Description & Mission
                                    </label>
                                    <textarea
                                        value={profileData.company_description || ''}
                                        onChange={(e) => setProfileData({ ...profileData, company_description: e.target.value })}
                                        placeholder="Tell candidates about your company culture, mission, and growth..."
                                        rows={4}
                                        className="w-full px-4 py-2.5 rounded-xl border border-slate-300 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 outline-none text-sm transition-all"
                                    />
                                </div>
                            </div>
                        )}

                        <div className="pt-2 flex justify-end">
                            <button
                                type="submit"
                                disabled={isSavingProfile}
                                className="btn btn-primary px-6 py-2.5 text-sm font-semibold flex items-center gap-2 rounded-xl shadow-sm hover:shadow"
                            >
                                {isSavingProfile ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                                Save {isCandidate ? 'Candidate Details' : 'Company Details'}
                            </button>
                        </div>
                    </form>

                    {isCandidate && (
                        <section className="card p-6 sm:p-7 border border-cyan-100 shadow-sm bg-white space-y-5">
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                                <div>
                                    <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                                        <Sparkles className="w-5 h-5 text-cyan-600" /> Resume insights
                                    </h3>
                                    <p className="text-xs text-slate-500 mt-1">
                                        Generate evidence-based strengths, skills, and practical next steps. If configured, relevant resume sections are sent to Anthropic after contact details are removed.
                                    </p>
                                </div>
                                <button
                                    type="button"
                                    onClick={handleGenerateInsights}
                                    disabled={!profileData.resume || profileData.resume instanceof File || isGeneratingInsights}
                                    className="btn btn-primary px-4 py-2.5 text-sm font-semibold flex items-center gap-2 rounded-xl disabled:opacity-50"
                                >
                                    {isGeneratingInsights ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                                    {isGeneratingInsights ? 'Analyzing…' : 'Analyze my resume'}
                                </button>
                            </div>
                            {profileData.resume instanceof File && (
                                <p className="text-xs text-amber-700">Save the replaced resume before analyzing it.</p>
                            )}
                            {resumeInsights && (
                                <div className="space-y-4 border-t border-slate-100 pt-4">
                                    <div className="rounded-xl bg-cyan-50 p-4 text-sm text-slate-800">
                                        <strong>Professional summary:</strong> {resumeInsights.professional_summary}
                                    </div>
                                    <p className="text-xs text-slate-500">
                                        {resumeInsights.generation_status === 'llm'
                                            ? `Generated with ${resumeInsights.model}; factual items are retained only when resume evidence is verified.`
                                            : 'Showing deterministic results; an LLM provider is not configured or could not return a valid response.'}
                                    </p>
                                    {resumeInsights.verified_skills?.length > 0 && (
                                        <div>
                                            <h4 className="text-sm font-semibold text-slate-800 mb-2">Verified skills</h4>
                                            <div className="flex flex-wrap gap-2">
                                                {resumeInsights.verified_skills.map((skill) => (
                                                    <span key={`${skill.skill}-${skill.evidence}`} title={skill.evidence} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
                                                        {skill.skill}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {resumeInsights.strengths?.length > 0 && (
                                        <div>
                                            <h4 className="text-sm font-semibold text-slate-800 mb-2">Strengths supported by your resume</h4>
                                            <ul className="space-y-2 text-sm text-slate-700">
                                                {resumeInsights.strengths.map((strength, index) => (
                                                    <li key={`${strength.claim}-${index}`}>
                                                        <strong>{strength.claim}</strong>
                                                        <p className="text-xs text-slate-500">Evidence: “{strength.evidence}”</p>
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}
                                    {resumeInsights.suggested_roles?.length > 0 && (
                                        <div>
                                            <h4 className="text-sm font-semibold text-slate-800 mb-2">Role categories to explore</h4>
                                            <div className="flex flex-wrap gap-2">
                                                {resumeInsights.suggested_roles.map((role) => (
                                                    <span key={role} className="rounded-full bg-indigo-50 px-3 py-1 text-xs text-indigo-800">{role}</span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {Object.entries(resumeInsights.verified_facts || {}).some(([, facts]) => facts.length > 0) && (
                                        <div>
                                            <h4 className="text-sm font-semibold text-slate-800 mb-2">Other evidence-checked details</h4>
                                            <div className="space-y-2 text-xs text-slate-700">
                                                {Object.entries(resumeInsights.verified_facts).map(([kind, facts]) => facts.length > 0 && (
                                                    <div key={kind}>
                                                        <strong className="capitalize">{kind}:</strong>{' '}
                                                        {facts.map((fact) => fact.claim || fact.skill).join('; ')}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {resumeInsights.improvement_recommendations?.length > 0 && (
                                        <div>
                                            <h4 className="text-sm font-semibold text-slate-800 mb-2">Next steps</h4>
                                            <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
                                                {resumeInsights.improvement_recommendations.map((item, index) => <li key={index}>{item}</li>)}
                                            </ul>
                                        </div>
                                    )}
                                </div>
                            )}
                        </section>
                    )}
                </div>
            </div>

            <ResumePreviewModal
                isOpen={isPreviewOpen}
                onClose={() => setIsPreviewOpen(false)}
                file={profileData.resume}
                fileName={resumeFileName || 'Profile Resume'}
            />
        </div>
    );
};

export default ProfilePage;
