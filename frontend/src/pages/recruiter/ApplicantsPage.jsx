import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../axios';
import { Users, FileText, Mail, Phone, ExternalLink, Loader2, ArrowLeft, CheckCircle, Sparkles, ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';
import AIMatchSummary from '../../components/AIMatchSummary';
import ResumePreviewModal from '../../components/ResumePreviewModal';

const ApplicantsPage = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [applications, setApplications] = useState([]);
    const [loading, setLoading] = useState(true);
    const [updating, setUpdating] = useState(null);
    const [expandedId, setExpandedId] = useState(null);
    const [summarizingId, setSummarizingId] = useState(null);
    const [summaryErrors, setSummaryErrors] = useState({});
    const [previewFile, setPreviewFile] = useState(null);
    const [previewName, setPreviewName] = useState('Resume');
    const [isPreviewOpen, setIsPreviewOpen] = useState(false);
    const [fetchingResumeId, setFetchingResumeId] = useState(null);

    const fetchApplicants = async () => {
        try {
            const response = await api.get('/applications/');
            setApplications(response.data.filter(app => Number(app.job) === Number(id)));
        } catch (error) {
            console.error('Failed to fetch applicants');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchApplicants();
    }, [id]);

    const handleStatusUpdate = async (appId, newStatus) => {
        setUpdating(appId);
        try {
            await api.patch(`/applications/${appId}/`, { status: newStatus });
            setApplications(applications.map(app =>
                app.id === appId ? { ...app, status: newStatus } : app
            ));
        } catch (err) {
            alert('Failed to update status.');
        } finally {
            setUpdating(null);
        }
    };

    const handleSummarize = async (appId, { regenerate = false } = {}) => {
        const app = applications.find((a) => a.id === appId);

        if (expandedId === appId && !regenerate) {
            setExpandedId(null);
            return;
        }

        if (app?.ai_summary && !regenerate) {
            setExpandedId(appId);
            return;
        }

        setSummarizingId(appId);
        setSummaryErrors((prev) => ({ ...prev, [appId]: null }));
        setExpandedId(appId);

        try {
            const response = await api.post(`/applications/${appId}/summarize/`, { regenerate });
            setApplications((prev) =>
                prev.map((a) =>
                    a.id === appId
                        ? { ...a, ai_summary: response.data.ai_summary, ai_summary_generated_at: response.data.ai_summary_generated_at }
                        : a
                )
            );
        } catch (err) {
            const message = err.response?.data?.detail || 'Failed to generate AI summary. Please try again.';
            setSummaryErrors((prev) => ({ ...prev, [appId]: message }));
        } finally {
            setSummarizingId(null);
        }
    };

    const handleViewResume = async (app) => {
        const endpoint = app.resume_url || (app.id ? `/api/applications/${app.id}/resume/` : null);
        if (!endpoint && !app.resume_snapshot) {
            alert('No resume attached to this application.');
            return;
        }

        setFetchingResumeId(app.id);

        try {
            const targetUrl = endpoint || app.resume_snapshot;
            const response = await api.get(targetUrl, { responseType: 'blob' });
            const contentType = response.headers['content-type'] || 'application/pdf';
            const blob = new Blob([response.data], { type: contentType });

            const safeName = (app.full_name || 'Candidate').trim().replace(/[^a-zA-Z0-9_-]/g, '_');
            let ext = '.pdf';
            if (contentType.includes('word') || contentType.includes('docx')) ext = '.docx';
            else if (contentType.includes('msword') || contentType.includes('doc')) ext = '.doc';

            setPreviewFile(blob);
            setPreviewName(`${safeName}_Resume${ext}`);
            setIsPreviewOpen(true);
        } catch (err) {
            console.error('Failed to load resume document:', err);
            const fallbackUrl = app.resume_url || app.resume_snapshot || (app.id ? `/api/applications/${app.id}/resume/` : null);
            if (fallbackUrl) {
                window.open(fallbackUrl, '_blank');
            } else {
                alert('Resume file could not be accessed. The applicant might not have uploaded a valid resume document.');
            }
        } finally {
            setFetchingResumeId(null);
        }
    };

    const getMatchColor = (score) => {
        if (score >= 75) return 'text-green-600 bg-green-50 border-green-200';
        if (score >= 50) return 'text-yellow-600 bg-yellow-50 border-yellow-200';
        return 'text-red-600 bg-red-50 border-red-200';
    };

    const getStatusBadge = (status) => {
        switch (status) {
            case 'ACCEPTED': return 'bg-green-100 text-green-700 border-green-200';
            case 'REJECTED': return 'bg-red-100 text-red-700 border-red-200';
            case 'SHORTLISTED': return 'bg-purple-100 text-purple-700 border-purple-200';
            case 'REVIEWING': return 'bg-yellow-100 text-yellow-700 border-yellow-200';
            default: return 'bg-gray-100 text-gray-700 border-gray-200';
        }
    };

    return (
        <div className="max-w-6xl mx-auto py-12 px-4 sm:px-6 lg:px-8 space-y-8 animate-fade-in">
            <button
                onClick={() => navigate(-1)}
                className="flex items-center gap-2 text-gray-500 hover:text-primary-600 transition-colors"
            >
                <ArrowLeft className="w-4 h-4" />
                Back to dashboard
            </button>

            <div className="flex items-center gap-4">
                <div className="p-4 bg-primary-600 rounded-2xl text-white shadow-lg shadow-primary-500/20">
                    <Users className="w-8 h-8" />
                </div>
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">Job Applicants</h1>
                    <p className="text-gray-500">Managing {applications.length} candidates for this position</p>
                </div>
            </div>

            {loading ? (
                <div className="flex justify-center py-20">
                    <Loader2 className="w-12 h-12 animate-spin text-primary-500" />
                </div>
            ) : applications.length === 0 ? (
                <div className="card py-20 text-center">
                    <Users className="w-16 h-16 text-gray-200 mx-auto mb-4" />
                    <h3 className="text-xl font-bold text-gray-900">No applicants yet</h3>
                    <p className="text-gray-500">When candidates apply, they will appear here.</p>
                </div>
            ) : (
                <div className="space-y-6">
                    {applications.map((app) => (
                        <div key={app.id} className="card overflow-hidden hover:shadow-xl transition-all duration-300">
                            <div className="flex flex-col md:flex-row gap-6 p-6">
                                <div className="flex-1 space-y-4">
                                    <div className="flex items-center justify-between">
                                        <h3 className="text-2xl font-bold text-gray-900">{app.full_name}</h3>
                                        <span className={`px-4 py-1 rounded-full text-xs font-bold border ${getStatusBadge(app.status)}`}>
                                            {app.status}
                                        </span>
                                    </div>

                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm text-gray-600">
                                        <div className="flex items-center gap-2">
                                            <Mail className="w-4 h-4 text-gray-400" /> {app.email}
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Phone className="w-4 h-4 text-gray-400" /> {app.phone_number}
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <ExternalLink className="w-4 h-4 text-gray-400" />
                                            <a href={app.linkedin_profile} target="_blank" rel="noreferrer" className="text-primary-600 hover:underline">LinkedIn Profile</a>
                                        </div>
                                    </div>

                                    <div className="p-4 bg-gray-50 rounded-xl">
                                        <p className="text-xs font-bold text-gray-400 uppercase mb-2">Education</p>
                                        <p className="font-medium">{app.university_name} - {app.major}</p>
                                        <p className="text-sm text-gray-500">{app.academic_level} | Class of {app.graduation_year}</p>
                                    </div>
                                </div>

                                <div className="md:w-64 flex flex-col gap-3 justify-center border-t md:border-t-0 md:border-l border-gray-100 pt-6 md:pt-0 md:pl-6">
                                    <button
                                        type="button"
                                        onClick={() => handleViewResume(app)}
                                        disabled={fetchingResumeId === app.id}
                                        className="btn btn-secondary flex items-center justify-center gap-2 py-2.5"
                                    >
                                        {fetchingResumeId === app.id ? (
                                            <Loader2 className="w-4 h-4 animate-spin text-primary-600" />
                                        ) : (
                                            <FileText className="w-4 h-4" />
                                        )}
                                        {fetchingResumeId === app.id ? 'Loading Resume...' : 'View Resume'}
                                    </button>

                                    <button
                                        onClick={() => handleSummarize(app.id)}
                                        disabled={summarizingId === app.id}
                                        className="btn flex items-center justify-center gap-2 py-2.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100"
                                    >
                                        {summarizingId === app.id ? (
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                        ) : (
                                            <Sparkles className="w-4 h-4" />
                                        )}
                                        {summarizingId === app.id
                                            ? 'Analyzing...'
                                            : expandedId === app.id
                                                ? 'Hide Summary'
                                                : app.ai_summary
                                                    ? 'View AI Summary'
                                                    : 'Summarize'}
                                        {expandedId === app.id ? (
                                            <ChevronUp className="w-4 h-4" />
                                        ) : (
                                            <ChevronDown className="w-4 h-4" />
                                        )}
                                    </button>

                                    <div className="grid grid-cols-2 gap-2">
                                        <button
                                            onClick={() => handleStatusUpdate(app.id, 'SHORTLISTED')}
                                            disabled={updating === app.id}
                                            className="btn bg-purple-50 text-purple-700 hover:bg-purple-100 text-xs py-2"
                                        >
                                            Shortlist
                                        </button>
                                        <button
                                            onClick={() => handleStatusUpdate(app.id, 'REJECTED')}
                                            disabled={updating === app.id}
                                            className="btn bg-red-50 text-red-700 hover:bg-red-100 text-xs py-2"
                                        >
                                            Reject
                                        </button>
                                    </div>
                                    <button
                                        onClick={() => handleStatusUpdate(app.id, 'ACCEPTED')}
                                        disabled={updating === app.id}
                                        className="btn bg-green-600 text-white hover:bg-green-700 flex items-center justify-center gap-2 py-2.5"
                                    >
                                        <CheckCircle className="w-4 h-4" />
                                        Hire Candidate
                                    </button>
                                </div>
                            </div>

                            {expandedId === app.id && (
                                <div className="border-t border-gray-100 bg-indigo-50/30 px-6 py-6">
                                    {summarizingId === app.id ? (
                                        <div className="flex items-center gap-3 text-indigo-700 py-4">
                                            <Loader2 className="w-5 h-5 animate-spin" />
                                            <span>Reading resume and comparing against the job description...</span>
                                        </div>
                                    ) : summaryErrors[app.id] ? (
                                        <div className="flex items-start gap-3 text-red-700 py-2">
                                            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                                            <div>
                                                <p className="font-medium">{summaryErrors[app.id]}</p>
                                                <button
                                                    onClick={() => handleSummarize(app.id, { regenerate: true })}
                                                    className="text-sm text-indigo-600 hover:underline mt-1"
                                                >
                                                    Try again
                                                </button>
                                            </div>
                                        </div>
                                    ) : app.ai_summary ? (
                                        <AIMatchSummary
                                            aiSummary={app.ai_summary}
                                            generatedAt={app.ai_summary_generated_at}
                                            onRegenerate={() => handleSummarize(app.id, { regenerate: true })}
                                            isRegenerating={summarizingId === app.id}
                                        />
                                    ) : null}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            <ResumePreviewModal
                isOpen={isPreviewOpen}
                onClose={() => {
                    setIsPreviewOpen(false);
                    setPreviewFile(null);
                }}
                file={previewFile}
                fileName={previewName}
            />
        </div>
    );
};

export default ApplicantsPage;
