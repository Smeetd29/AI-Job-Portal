import { useState, useEffect, useRef } from 'react';
import api from '../../axios';
import { Search, MapPin, DollarSign, Filter, Briefcase, ChevronRight, Loader2, Bookmark, ChevronDown } from 'lucide-react';
import { Link } from 'react-router-dom';

const CandidateDashboard = () => {
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [filters, setFilters] = useState({
        category: '',
        job_type: '',
        min_pay: '',
    });
    const [viewMode, setViewMode] = useState('explore');
    const [savedJobs, setSavedJobs] = useState([]);
    const [savedMap, setSavedMap] = useState({});
    const [applications, setApplications] = useState([]);
    const [menuOpen, setMenuOpen] = useState(false);
    const menuRef = useRef(null);

    const fetchJobs = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (search) params.append('search', search);
            if (filters.category) params.append('category', filters.category);
            if (filters.job_type) params.append('job_type', filters.job_type);
            if (filters.min_pay) params.append('min_pay', filters.min_pay);

            const response = await api.get(`/jobs/?${params.toString()}`);
            const jobData = response.data.results || response.data;
            const list = Array.isArray(jobData) ? jobData : [];
            if (Object.keys(savedMap).length) {
                setJobs(list.map(j => ({ ...j, is_saved: !!savedMap[j.id] })));
            } else {
                setJobs(list);
            }
        } catch (error) {
            console.error('Failed to fetch jobs', error);
            setJobs([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        const timeout = setTimeout(fetchJobs, 300);
        return () => clearTimeout(timeout);
    }, [search, filters]);

    useEffect(() => {
        const fetchSavedJobsOnMount = async () => {
            try {
                const res = await api.get('/saved-jobs/');
                const data = res.data.results || res.data || [];
                setSavedJobs(data);
                const map = {};
                data.forEach(s => {
                    const job = s.job || s.job_details;
                    if (job && job.id) map[job.id] = s.id;
                });
                setSavedMap(map);
            } catch (err) {
                console.error('Failed to fetch saved jobs', err);
            }
        };
        fetchSavedJobsOnMount();
    }, []);

    useEffect(() => {
        if (viewMode === 'saved') {
            fetchSavedJobs();
        } else if (viewMode === 'applications') {
            (async () => {
                const data = await fetchApplications();
                setApplications(data);
            })();
        }
    }, [viewMode]);

    useEffect(() => {
        const handleClick = (e) => {
            if (menuRef.current && !menuRef.current.contains(e.target)) {
                setMenuOpen(false);
            }
        };
        const handleEsc = (e) => {
            if (e.key === 'Escape') setMenuOpen(false);
        };
        document.addEventListener('click', handleClick);
        document.addEventListener('keydown', handleEsc);
        return () => {
            document.removeEventListener('click', handleClick);
            document.removeEventListener('keydown', handleEsc);
        };
    }, []);

    const fetchSavedJobs = async () => {
        try {
            const res = await api.get('/saved-jobs/');
            const data = res.data.results || res.data || [];
            setSavedJobs(data);
            const map = {};
            data.forEach(s => {
                const job = s.job || s.job_details;
                if (job && job.id) map[job.id] = s.id;
            });
            setSavedMap(map);
            setJobs(prev => prev.map(j => ({ ...j, is_saved: !!map[j.id] })));
        } catch (err) {
            console.error('Failed to fetch saved jobs', err);
        }
    };

    const handleToggleSave = async (e, job) => {
        e.preventDefault();
        e.stopPropagation();
        try {
            if (job.is_saved) {
                const savedId = savedMap[job.id];
                if (!savedId) {
                    await fetchSavedJobs();
                    return;
                }
                await api.delete(`/saved-jobs/${savedId}/`);
                setSavedMap(prev => {
                    const next = { ...prev };
                    delete next[job.id];
                    return next;
                });
                setJobs(prev => prev.map(j => j.id === job.id ? { ...j, is_saved: false } : j));
                setSavedJobs(prev => prev.filter(s => (s.job || s.job_details)?.id !== job.id));
            } else {
                const res = await api.post('/saved-jobs/', { job: job.id });
                const saved = res.data;
                setSavedMap(prev => ({ ...prev, [job.id]: saved.id }));
                setJobs(prev => prev.map(j => j.id === job.id ? { ...j, is_saved: true } : j));
                setSavedJobs(prev => [saved, ...prev]);
            }
        } catch (err) {
            console.error('Failed to toggle save', err);
        }
    };

    const fetchApplications = async () => {
        try {
            const res = await api.get('/applications/');
            const data = res.data.results || res.data || [];
            return data;
        } catch (err) {
            console.error('Failed to fetch applications', err);
            return [];
        }
    };

    return (
        <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-10 xl:px-12 py-2 animate-fade-in">
            <div className="sticky top-20 z-20 bg-gray-50/95 backdrop-blur-md py-4 border-b border-slate-200/80 mb-6">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-4">
                            <div>
                                <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
                                    {viewMode === 'explore' ? 'Explore Jobs' : viewMode === 'saved' ? 'Saved Jobs' : 'Application Status'}
                                </h1>
                                <p className="text-xs sm:text-sm text-gray-500">Find the perfect role for your next career move</p>
                            </div>
                            <div className="relative" ref={menuRef}>
                                <div className="inline-block">
                                    <button className="btn btn-secondary px-3 py-2 flex items-center gap-2" onClick={() => setMenuOpen(prev => !prev)}>
                                        <span>Menu</span>
                                        <ChevronDown className={`w-4 h-4 transition-transform ${menuOpen ? 'rotate-180' : ''}`} />
                                    </button>
                                    {menuOpen && (
                                        <div className="mt-2 w-48 bg-white rounded-xl border border-slate-200 shadow-lg z-30 absolute left-0">
                                            <button className={`w-full text-left px-4 py-2 hover:bg-slate-50 ${viewMode === 'explore' ? 'bg-slate-50 font-semibold text-primary-600' : ''}`} onClick={() => { setViewMode('explore'); fetchJobs(); setMenuOpen(false); }}>
                                                Explore Jobs
                                            </button>
                                            <button className={`w-full text-left px-4 py-2 hover:bg-slate-50 ${viewMode === 'saved' ? 'bg-slate-50 font-semibold text-primary-600' : ''}`} onClick={async () => { setViewMode('saved'); await fetchSavedJobs(); setMenuOpen(false); }}>
                                                Saved Jobs
                                            </button>
                                            <button className={`w-full text-left px-4 py-2 hover:bg-slate-50 ${viewMode === 'applications' ? 'bg-slate-50 font-semibold text-primary-600' : ''}`} onClick={async () => { setViewMode('applications'); setMenuOpen(false); }}>
                                                Application Status
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="relative group flex-1 max-w-md">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 group-focus-within:text-primary-500 transition-colors w-5 h-5" />
                        <input
                            type="text"
                            placeholder="Search jobs by title, skill, or category..."
                            className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-200 focus:ring-4 focus:ring-primary-500/10 focus:border-primary-500 outline-none transition-all shadow-sm bg-white"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                </div>
            </div>

            <div className="flex flex-col lg:flex-row gap-6 lg:h-[calc(100vh-210px)] lg:overflow-hidden">
                <div className="flex-1 lg:overflow-y-auto lg:pr-3 space-y-3 scroll-smooth">
                    {loading ? (
                        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
                            <Loader2 className="w-10 h-10 animate-spin mb-4 text-primary-500" />
                            <p className="font-medium">Finding the best jobs for you...</p>
                        </div>
                    ) : viewMode === 'saved' ? (
                        <div className="space-y-3">
                            {savedJobs.length === 0 ? (
                                <div className="card py-12 text-center">
                                    <p className="text-slate-500">You haven't saved any jobs yet.</p>
                                </div>
                            ) : (
                                savedJobs.map(s => {
                                    const job = s.job_details || s.job;
                                    return (
                                        <Link key={s.id} to={`/jobs/${job.id}`} className="card group flex flex-col gap-3 border border-slate-200 p-4 transition duration-200 hover:border-primary-500/50 hover:shadow-sm">
                                            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                                <div className="flex-1">
                                                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                                                        <h3 className="text-base font-semibold text-slate-900 transition-colors group-hover:text-primary-600">{job.title}</h3>
                                                        <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold ${job.job_type === 'Full Time' ? 'bg-green-50 text-green-700' :
                                                                job.job_type === 'Part Time' ? 'bg-blue-50 text-blue-700' :
                                                                    'bg-gray-100 text-gray-700'
                                                            }`}>{job.job_type}</span>
                                                    </div>
                                                    <p className="text-sm text-slate-500 line-clamp-2">{job.description}</p>
                                                </div>
                                                <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-slate-100 sm:h-16 sm:w-16">
                                                    <Briefcase className="h-6 w-6 text-slate-500" />
                                                </div>
                                            </div>
                                            <div className="flex items-center justify-between mt-2">
                                                <div className="grid gap-2 text-sm text-slate-500 sm:grid-cols-3 w-full">
                                                    <div className="inline-flex items-center gap-2">
                                                        <MapPin className="h-4 w-4 text-slate-400" />
                                                        <span>{job.location || 'Remote'}</span>
                                                    </div>
                                                    <div className="inline-flex items-center gap-2">
                                                        <DollarSign className="h-4 w-4 text-slate-400" />
                                                        <span>{job.pay_amount}</span>
                                                    </div>
                                                    <div className="inline-flex items-center gap-2 font-medium text-primary-600 justify-start sm:justify-end">Apply <ChevronRight className="h-4 w-4" /></div>
                                                </div>
                                                <div className="ml-4">
                                                    <button onClick={(e) => handleToggleSave(e, job)} className="inline-flex items-center gap-2 rounded-xl px-3 py-1 text-sm font-medium bg-primary-600 text-white">
                                                        <Bookmark className="w-4 h-4" />
                                                        <span>Unsave</span>
                                                    </button>
                                                </div>
                                            </div>
                                        </Link>
                                    )
                                })
                            )}
                        </div>
                    ) : viewMode === 'applications' ? (
                        <div className="space-y-3">
                            {applications.length === 0 ? (
                                <div className="card py-12 text-center">
                                    <p className="text-slate-500">You have no applications yet.</p>
                                </div>
                            ) : (
                                applications.map(app => (
                                    <div key={app.id} className="card flex items-center justify-between p-4">
                                        <div>
                                            <h3 className="font-semibold text-slate-900">{app.job_title || app.job?.title}</h3>
                                            <p className="text-sm text-slate-500">Status: <span className="font-medium text-primary-600">{app.status}</span></p>
                                        </div>
                                        <div className="text-sm text-slate-500">Applied: {new Date(app.applied_at).toLocaleDateString()}</div>
                                    </div>
                                ))
                            )}
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {jobs.map((job) => (
                                <Link
                                    key={job.id}
                                    to={`/jobs/${job.id}`}
                                    className="card group flex flex-col gap-3 border border-slate-200 p-4 transition duration-200 hover:border-primary-500/50 hover:shadow-sm"
                                >
                                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                        <div className="flex-1">
                                            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                                                <h3 className="text-base font-semibold text-slate-900 transition-colors group-hover:text-primary-600">
                                                    {job.title}
                                                </h3>
                                                <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold ${job.job_type === 'Full Time' ? 'bg-green-50 text-green-700' :
                                                        job.job_type === 'Part Time' ? 'bg-blue-50 text-blue-700' :
                                                            'bg-gray-100 text-gray-700'
                                                    }`}>
                                                    {job.job_type}
                                                </span>
                                            </div>
                                            <p className="text-sm text-slate-500 line-clamp-2">
                                                {job.description}
                                            </p>
                                        </div>
                                        <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-slate-100 sm:h-16 sm:w-16">
                                            <Briefcase className="h-6 w-6 text-slate-500" />
                                        </div>
                                    </div>

                                    <div className="flex items-center justify-between mt-2">
                                        <div className="grid gap-2 text-sm text-slate-500 sm:grid-cols-3 w-full">
                                            <div className="inline-flex items-center gap-2">
                                                <MapPin className="h-4 w-4 text-slate-400" />
                                                <span>{job.location || 'Remote'}</span>
                                            </div>
                                            <div className="inline-flex items-center gap-2">
                                                <DollarSign className="h-4 w-4 text-slate-400" />
                                                <span>{job.pay_amount}</span>
                                            </div>
                                            <div className="inline-flex items-center gap-2 font-medium text-primary-600 justify-start sm:justify-end">
                                                Apply <ChevronRight className="h-4 w-4" />
                                            </div>
                                        </div>

                                        <div className="ml-4">
                                            <button onClick={(e) => handleToggleSave(e, job)} className={`inline-flex items-center gap-2 rounded-xl px-3 py-1 text-sm font-medium ${job.is_saved ? 'bg-primary-600 text-white' : 'bg-white border border-slate-200 text-slate-700'}`}>
                                                <Bookmark className="w-4 h-4" />
                                                <span>{job.is_saved ? 'Saved' : 'Save'}</span>
                                            </button>
                                        </div>
                                    </div>
                                </Link>
                            ))}
                        </div>
                    )}
                </div>

                <aside className="w-full lg:w-80 xl:w-96 flex-shrink-0 lg:overflow-y-auto pr-1">
                    <div className="card border border-slate-200 p-6 shadow-sm">
                        <div className="flex items-center gap-2 mb-6">
                            <Filter className="h-5 w-5 text-primary-600" />
                            <h2 className="text-xl font-semibold text-slate-900">Filters</h2>
                        </div>
                        <div className="space-y-5">
                            <div>
                                <p className="text-sm text-slate-500 mb-2">Category</p>
                                <select
                                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-500/10"
                                    value={filters.category}
                                    onChange={(e) => setFilters({ ...filters, category: e.target.value })}
                                >
                                    <option value="">All Categories</option>
                                    <option value="Engineering">Engineering</option>
                                    <option value="Design">Design</option>
                                    <option value="Marketing">Marketing</option>
                                    <option value="Sales">Sales</option>
                                </select>
                            </div>

                            <div>
                                <p className="text-sm text-slate-500 mb-2">Job type</p>
                                <select
                                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-500/10"
                                    value={filters.job_type}
                                    onChange={(e) => setFilters({ ...filters, job_type: e.target.value })}
                                >
                                    <option value="">All types</option>
                                    <option value="Full Time">Full time</option>
                                    <option value="Part Time">Part time</option>
                                    <option value="Contract">Contract</option>
                                    <option value="Freelance">Freelance</option>
                                </select>
                            </div>

                            <div>
                                <p className="text-sm text-slate-500 mb-2">Minimum salary</p>
                                <input
                                    type="number"
                                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-500/10"
                                    placeholder="Any"
                                    value={filters.min_pay}
                                    onChange={(e) => setFilters({ ...filters, min_pay: e.target.value })}
                                />
                            </div>

                            <div className="flex gap-3">
                                <button
                                    className="flex-1 rounded-xl bg-primary-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary-700"
                                    onClick={fetchJobs}
                                >
                                    Apply filters
                                </button>
                                <button
                                    className="flex-1 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                                    onClick={() => setFilters({ category: '', job_type: '', min_pay: '' })}
                                >
                                    Reset
                                </button>
                            </div>
                        </div>
                    </div>
                </aside>
            </div>
        </div>
    );
};

export default CandidateDashboard;
