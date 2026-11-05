import { useState, useEffect } from 'react';
import api from '../../axios';
import { Plus, Users, Briefcase, ChevronRight, Loader2, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';

const RecruiterDashboard = () => {
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchMyJobs = async () => {
        try {
            const response = await api.get('/jobs/?manage=true');
            setJobs(response.data);
        } catch (error) {
            console.error('Failed to fetch jobs');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchMyJobs();
    }, []);

    const handleDelete = async (id) => {
        if (window.confirm('Are you sure you want to delete this job?')) {
            try {
                await api.delete(`/jobs/${id}/`, {
                    withCredentials: true
                });
                setJobs(jobs.filter(job => job.id !== id));
            } catch (err) {
                alert('Failed to delete job.');
            }
        }
    };

    return (
        <div className="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8 space-y-8 animate-fade-in">
            <div className="flex justify-between items-end">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">Recruiter Dashboard</h1>
                    <p className="text-gray-500">Manage your job postings and applicants</p>
                </div>
                <Link to="/recruiter/create-job" className="btn btn-primary flex items-center gap-2">
                    <Plus className="w-5 h-5" />
                    Post New Job
                </Link>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="card flex items-center gap-4 bg-primary-50 border-primary-100">
                    <div className="p-3 bg-primary-600 rounded-xl text-white">
                        <Briefcase className="w-6 h-6" />
                    </div>
                    <div>
                        <p className="text-sm text-primary-600 font-medium">Total Postings</p>
                        <p className="text-2xl font-bold text-primary-900">{jobs.length}</p>
                    </div>
                </div>
                <div className="card flex items-center gap-4 bg-green-50 border-green-100">
                    <div className="p-3 bg-green-600 rounded-xl text-white">
                        <Users className="w-6 h-6" />
                    </div>
                    <div>
                        <p className="text-sm text-green-600 font-medium">Total Applicants</p>
                        <p className="text-2xl font-bold text-green-900">
                            {jobs.reduce((acc, job) => acc + (job.applications_count || 0), 0)}
                        </p>
                    </div>
                </div>
            </div>

            <div className="space-y-4">
                <h2 className="text-xl font-bold text-gray-900">Your Active Jobs</h2>
                {loading ? (
                    <div className="flex justify-center py-20">
                        <Loader2 className="w-10 h-10 animate-spin text-primary-500" />
                    </div>
                ) : jobs.length === 0 ? (
                    <div className="card py-20 text-center">
                        <Briefcase className="w-16 h-16 text-gray-200 mx-auto mb-4" />
                        <h3 className="text-xl font-bold text-gray-900">No jobs posted yet</h3>
                        <p className="text-gray-500 mb-6">Start by creating your first job listing.</p>
                        <Link to="/recruiter/create-job" className="btn btn-primary">Create Job</Link>
                    </div>
                ) : (
                    <div className="overflow-hidden card !p-0">
                        <table className="w-full text-left">
                            <thead className="bg-gray-50 border-b border-gray-100">
                                <tr>
                                    <th className="px-6 py-4 text-xs font-bold text-gray-400 uppercase tracking-wider">Job Title</th>
                                    <th className="px-6 py-4 text-xs font-bold text-gray-400 uppercase tracking-wider">Type</th>
                                    <th className="px-6 py-4 text-xs font-bold text-gray-400 uppercase tracking-wider">Applicants</th>
                                    <th className="px-6 py-4 text-xs font-bold text-gray-400 uppercase tracking-wider text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {jobs.map((job) => (
                                    <tr key={job.id} className="hover:bg-gray-50 transition-colors group">
                                        <td className="px-6 py-4">
                                            <div className="font-bold text-gray-900">{job.title}</div>
                                            <div className="text-xs text-gray-500 mt-1">Posted on {new Date(job.created_at).toLocaleDateString()}</div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className="px-2.5 py-1 rounded-full bg-gray-100 text-gray-700 text-xs font-bold">
                                                {job.job_type.replace('_', ' ')}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            <Link
                                                to={`/recruiter/jobs/${job.id}/applicants`}
                                                className="flex items-center gap-2 text-primary-600 font-bold hover:underline"
                                            >
                                                {job.applications_count || 0} Applicants
                                                <ChevronRight className="w-4 h-4" />
                                            </Link>
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                                <button
                                                    onClick={() => handleDelete(job.id)}
                                                    className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
};

export default RecruiterDashboard;
