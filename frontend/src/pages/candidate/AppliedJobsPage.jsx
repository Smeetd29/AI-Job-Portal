import { useState, useEffect } from 'react';
import api from '../../axios';
import { Briefcase, Clock, ChevronRight, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';

const AppliedJobsPage = () => {
    const [applications, setApplications] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchApplications = async () => {
        try {
            const response = await api.get('/applications/');
            const data = response.data.results || response.data || [];
            setApplications(Array.isArray(data) ? data : []);
        } catch (error) {
            console.error('Failed to fetch applications', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchApplications();
    }, []);

    const getStatusColor = (status) => {
        switch (status) {
            case 'ACCEPTED': return 'bg-green-100 text-green-700';
            case 'REJECTED': return 'bg-red-100 text-red-700';
            case 'SHORTLISTED': return 'bg-blue-100 text-blue-700';
            case 'REVIEWING': return 'bg-yellow-100 text-yellow-700';
            default: return 'bg-gray-100 text-gray-700';
        }
    };

    return (
        <div className="max-w-5xl mx-auto py-12 px-4 sm:px-6 lg:px-8 space-y-8 animate-fade-in">
            <div>
                <h1 className="text-3xl font-bold text-gray-900">Applied Jobs</h1>
                <p className="text-gray-500">Track the status of your applications</p>
            </div>

            {loading ? (
                <div className="flex justify-center py-20">
                    <Loader2 className="w-10 h-10 animate-spin text-primary-500" />
                </div>
            ) : applications.length === 0 ? (
                <div className="card py-20 text-center">
                    <Briefcase className="w-16 h-16 text-gray-200 mx-auto mb-4" />
                    <h3 className="text-xl font-bold text-gray-900">No applications yet</h3>
                    <p className="text-gray-500 mb-6">You haven't applied to any jobs yet.</p>
                    <Link to="/candidate" className="btn btn-primary">Browse Jobs</Link>
                </div>
            ) : (
                <div className="space-y-4">
                    {applications.map((app) => (
                        <div key={app.id} className="card flex items-center justify-between group hover:border-primary-500/50 transition-all">
                            <div className="flex items-center gap-6">
                                <div className="p-4 bg-gray-50 rounded-xl group-hover:bg-primary-50 transition-colors">
                                    <Briefcase className="w-6 h-6 text-gray-400 group-hover:text-primary-600" />
                                </div>
                                <div>
                                    <h3 className="text-lg font-bold text-gray-900 group-hover:text-primary-600">
                                        {app.job_title || app.job_details?.title || 'Job Title'}
                                    </h3>
                                    <div className="flex items-center gap-4 text-sm text-gray-500 mt-1">
                                        {(app.company_name || app.job_details?.company) && (
                                            <span className="font-semibold text-slate-700">
                                                {app.company_name || app.job_details?.company}
                                            </span>
                                        )}
                                        <span className="flex items-center gap-1.5"><Clock className="w-4 h-4" /> {new Date(app.applied_at).toLocaleDateString()}</span>
                                    </div>
                                </div>
                            </div>

                            <div className="flex items-center gap-6">
                                <span className={`px-3 py-1 rounded-full text-xs font-bold ${getStatusColor(app.status)}`}>
                                    {app.status}
                                </span>
                                <Link to={`/jobs/${app.job}`} className="p-2 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-all">
                                    <ChevronRight className="w-6 h-6" />
                                </Link>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default AppliedJobsPage;
