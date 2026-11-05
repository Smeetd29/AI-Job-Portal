import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../axios';
import { Briefcase, MapPin, DollarSign, Calendar, Clock, Send, CheckCircle, AlertCircle, Loader2, ArrowLeft } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import ApplicationModal from '../../components/candidate/ApplicationModal';

const JobDetailsPage = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const { user } = useAuth();
    const [job, setJob] = useState(null);
    const [loading, setLoading] = useState(true);
    const [applied, setApplied] = useState(false);
    const [error, setError] = useState('');
    const [showForm, setShowForm] = useState(false);

    const fetchJob = async () => {
        try {
            const response = await api.get(`/jobs/${id}/`);
            setJob(response.data);
            const appsResponse = await api.get('/applications/');
            if (appsResponse.data.some(app => app.job === parseInt(id))) {
                setApplied(true);
            }
        } catch (err) {
            console.error('Failed to fetch job');
            navigate('/candidate');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchJob();
    }, [id]);

    if (loading) return (
        <div className="min-h-screen flex items-center justify-center">
            <Loader2 className="w-12 h-12 animate-spin text-primary-500" />
        </div>
    );

    if (!job) return null;

    return (
        <>
            <ApplicationModal
                isOpen={showForm}
                onClose={() => setShowForm(false)}
                job={job}
                user={user}
                onApplySuccess={() => setApplied(true)}
            />

            <div className="max-w-4xl mx-auto py-12 px-4 sm:px-6 lg:px-8 space-y-8 animate-fade-in">
                <button
                    onClick={() => navigate(-1)}
                    className="flex items-center gap-2 text-gray-500 hover:text-primary-600 transition-colors"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Back to jobs
                </button>

                <div className="card !p-0 overflow-hidden">
                    <div className="bg-primary-600 p-8 text-white">
                        <div className="flex justify-between items-start gap-4">
                            <div>
                                <h1 className="text-3xl font-bold mb-2">{job.title}</h1>
                                <div className="flex flex-wrap gap-4 text-primary-100 italic">
                                    <span className="flex items-center gap-1.5"><Briefcase className="w-4 h-4" /> {job.category}</span>
                                    <span className="flex items-center gap-1.5"><MapPin className="w-4 h-4" /> {job.location || 'Remote'}</span>
                                </div>
                            </div>
                            <span className="bg-white/20 backdrop-blur-md px-4 py-1.5 rounded-full text-sm font-bold border border-white/30">
                                {job.job_type?.replace('_', ' ')}
                            </span>
                        </div>
                    </div>

                    <div className="p-8 space-y-8">
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                            <div className="p-4 bg-gray-50 rounded-xl">
                                <p className="text-xs font-semibold text-gray-400 uppercase mb-1">Salary</p>
                                <p className="font-bold flex items-center gap-1"><DollarSign className="w-4 h-4 text-green-600" /> {job.pay_amount}</p>
                            </div>
                            <div className="p-4 bg-gray-50 rounded-xl">
                                <p className="text-xs font-semibold text-gray-400 uppercase mb-1">Pay Mode</p>
                                <p className="font-bold flex items-center gap-1"><Clock className="w-4 h-4 text-primary-600" /> {job.pay_mode}</p>
                            </div>
                            <div className="p-4 bg-gray-50 rounded-xl">
                                <p className="text-xs font-semibold text-gray-400 uppercase mb-1">Posted On</p>
                                <p className="font-bold flex items-center gap-1"><Calendar className="w-4 h-4 text-orange-600" /> {new Date(job.created_at).toLocaleDateString()}</p>
                            </div>
                            <div className="p-4 bg-gray-50 rounded-xl">
                                <p className="text-xs font-semibold text-gray-400 uppercase mb-1">Experience</p>
                                <p className="font-bold">{job.experience_level || 'Entry'}</p>
                            </div>
                        </div>

                        <div className="prose max-w-none text-gray-600">
                            <h2 className="text-xl font-bold text-gray-900 border-b pb-2 mb-4">Job Description</h2>
                            <div className="whitespace-pre-wrap">{job.description}</div>
                        </div>

                        <div className="pt-6 border-t">
                            {error && (
                                <div className="mb-4 bg-red-50 text-red-700 p-4 rounded-lg flex items-center gap-2">
                                    <AlertCircle className="w-5 h-5" /> {error}
                                </div>
                            )}

                            {applied ? (
                                <div className="bg-green-50 text-green-700 p-6 rounded-xl flex items-center justify-center gap-3 font-bold border border-green-100">
                                    <CheckCircle className="w-6 h-6" />
                                    You have already applied to this position
                                </div>
                            ) : (
                                <>
                                    {!showForm && (
                                        <button
                                            onClick={() => { setShowForm(true); setError(''); }}
                                            disabled={user?.is_recruiter}
                                            className="btn btn-primary w-full max-w-xs py-4 text-lg shadow-xl hover:shadow-primary-600/30 flex items-center justify-center gap-3 mx-auto"
                                        >
                                            <Send className="w-6 h-6" />
                                            Apply Now
                                        </button>
                                    )}
                                </>
                            )}

                            {user?.is_recruiter && (
                                <p className="text-center text-sm text-gray-400 mt-4 italic">
                                    Recruiters cannot apply to jobs.
                                </p>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
};

export default JobDetailsPage;
