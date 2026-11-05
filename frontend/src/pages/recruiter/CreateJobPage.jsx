import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../axios';
import { Briefcase, MapPin, DollarSign, FileText, Plus, ChevronLeft, AlertCircle } from 'lucide-react';
import { Link } from 'react-router-dom';

const CreateJobPage = () => {
    const navigate = useNavigate();
    const [isLoading, setIsLoading] = useState(false);
    const [fieldErrors, setFieldErrors] = useState({});
    const [error, setError] = useState('');

    const [formData, setFormData] = useState({
        title: '',
        description: '',
        category: 'Engineering',
        job_type: 'Full Time',
        location_type: 'Onsite',
        pay_amount: '',
        pay_mode: 'Monthly',
    });

    const categories = [
        'Engineering', 'Design', 'Marketing', 'Sales',
        'Product', 'Customer Support', 'Finance', 'Operations'
    ];

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
        if (fieldErrors[name]) {
            setFieldErrors(prev => {
                const newErrors = { ...prev };
                delete newErrors[name];
                return newErrors;
            });
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        setError('');
        setFieldErrors({});

        try {
            const dataToSubmit = {
                ...formData,
                pay_amount: parseFloat(formData.pay_amount)
            };
            await api.post('/jobs/', dataToSubmit);
            navigate('/recruiter');
        } catch (err) {
            console.error('Job creation failed', err);
            if (err.response?.data) {
                setFieldErrors(err.response.data);
                setError('Please fix the errors below.');
            } else {
                setError('Failed to create job. Please check your connection.');
            }
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="max-w-4xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
            <Link
                to="/recruiter"
                className="inline-flex items-center text-sm font-medium text-gray-500 hover:text-primary-600 mb-8 transition-colors"
            >
                <ChevronLeft className="w-4 h-4 mr-1" /> Back to Dashboard
            </Link>

            <div className="bg-white rounded-2xl shadow-xl border border-gray-100 overflow-hidden">
                <div className="bg-gradient-to-r from-primary-600 to-primary-700 px-8 py-10 text-white">
                    <h1 className="text-3xl font-extrabold flex items-center gap-3">
                        <Plus className="w-8 h-8 p-1.5 bg-white/20 rounded-lg" />
                        Post a New Job
                    </h1>
                    <p className="mt-2 text-primary-100 italic opacity-90 text-lg">
                        Reach the best talent by providing clear and attractive job details.
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="p-8 space-y-8">
                    {error && (
                        <div className="p-4 rounded-xl bg-red-50 border border-red-100 text-red-700 flex flex-col gap-2 animate-shake">
                            <div className="flex items-center gap-3">
                                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                                <p className="text-sm font-bold">{error}</p>
                            </div>
                            {fieldErrors && Object.keys(fieldErrors).length > 0 && typeof fieldErrors === 'object' && (
                                <pre className="text-[10px] mt-2 p-2 bg-red-100/50 rounded overflow-auto max-h-32">
                                    {JSON.stringify(fieldErrors, null, 2)}
                                </pre>
                            )}
                        </div>
                    )}

                    <div className="space-y-6">
                        <div className="grid grid-cols-1 gap-6">
                            <div>
                                <label className="block text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
                                    <FileText className="w-4 h-4 text-primary-500" />
                                    Job Title
                                </label>
                                <input
                                    type="text"
                                    name="title"
                                    required
                                    placeholder="e.g. Senior React Developer"
                                    className={`input-field ${fieldErrors.title ? 'border-red-500 ring-red-500/10' : ''}`}
                                    value={formData.title}
                                    onChange={handleChange}
                                />
                                {fieldErrors.title && <p className="mt-1 text-xs text-red-500 font-medium">{fieldErrors.title[0]}</p>}
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div>
                                    <label className="block text-sm font-bold text-gray-700 mb-2">Category</label>
                                    <select
                                        name="category"
                                        className="input-field"
                                        value={formData.category}
                                        onChange={handleChange}
                                    >
                                        {categories.map(cat => (
                                            <option key={cat} value={cat}>{cat}</option>
                                        ))}
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
                                        <Briefcase className="w-4 h-4 text-primary-500" />
                                        Job Type
                                    </label>
                                    <select
                                        name="job_type"
                                        className="input-field"
                                        value={formData.job_type}
                                        onChange={handleChange}
                                    >
                                        <option value="Full Time">Full Time</option>
                                        <option value="Part Time">Part Time</option>
                                        <option value="Contract">Contract</option>
                                        <option value="Freelance">Freelance</option>
                                    </select>
                                </div>
                            </div>
                        </div>

                        <hr className="border-gray-100" />

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                                <label className="block text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
                                    <MapPin className="w-4 h-4 text-primary-500" />
                                    Location Type
                                </label>
                                <select
                                    name="location_type"
                                    className="input-field"
                                    value={formData.location_type}
                                    onChange={handleChange}
                                >
                                    <option value="Onsite">Onsite</option>
                                    <option value="Remote">Remote</option>
                                    <option value="Hybrid">Hybrid</option>
                                </select>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div className="col-span-1">
                                    <label className="block text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
                                        <DollarSign className="w-4 h-4 text-primary-500" />
                                        Amount
                                    </label>
                                    <input
                                        type="number"
                                        name="pay_amount"
                                        required
                                        placeholder="0.00"
                                        className={`input-field ${fieldErrors.pay_amount ? 'border-red-500' : ''}`}
                                        value={formData.pay_amount}
                                        onChange={handleChange}
                                    />
                                    {fieldErrors.pay_amount && <p className="mt-1 text-xs text-red-500 font-medium">{fieldErrors.pay_amount[0]}</p>}
                                </div>
                                <div className="col-span-1">
                                    <label className="block text-sm font-bold text-gray-700 mb-2">Cycle</label>
                                    <select
                                        name="pay_mode"
                                        className="input-field"
                                        value={formData.pay_mode}
                                        onChange={handleChange}
                                    >
                                        <option value="Monthly">Monthly</option>
                                        <option value="Weekly">Weekly</option>
                                        <option value="Hourly">Hourly</option>
                                        <option value="One-time">One-time</option>
                                    </select>
                                </div>
                            </div>
                        </div>

                        <hr className="border-gray-100" />

                        <div>
                            <label className="block text-sm font-bold text-gray-700 mb-2">Job Description</label>
                            <textarea
                                name="description"
                                required
                                rows="6"
                                placeholder="Describe the role, responsibilities, and requirements..."
                                className={`input-field resize-none ${fieldErrors.description ? 'border-red-500' : ''}`}
                                value={formData.description}
                                onChange={handleChange}
                            ></textarea>
                            {fieldErrors.description && <p className="mt-1 text-xs text-red-500 font-medium">{fieldErrors.description[0]}</p>}
                        </div>
                    </div>

                    <div className="pt-4">
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="w-full btn-primary py-4 text-lg shadow-lg hover:shadow-2xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                        >
                            {isLoading ? (
                                <>
                                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                    Publishing...
                                </>
                            ) : 'Publish Job Listing'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default CreateJobPage;
