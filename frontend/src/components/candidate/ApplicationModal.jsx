import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X, Send, AlertCircle, Loader2, Sparkles } from 'lucide-react';
import api from '../../axios';
import ResumePreviewModal from '../ResumePreviewModal';

const AutofillBanner = ({ hasProfileResume, hasUploadedResume, onTriggerAutofill, autofilling, autofillSuccess }) => (
    <div className="bg-gradient-to-r from-indigo-50 to-blue-50 border border-indigo-100 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-600 shrink-0" />
            <div>
                <h4 className="text-sm font-semibold text-gray-900">Resume Autofill {autofillSuccess && <span className="text-xs text-green-700 bg-green-100 px-2 py-0.5 rounded-full">Populated</span>}</h4>
                <p className="text-xs text-gray-600">Auto-populate your application form from your resume.</p>
            </div>
        </div>
        {autofilling ? (
            <div className="flex items-center gap-2 text-xs font-semibold text-indigo-700"><Loader2 className="w-4 h-4 animate-spin" /> Extracting...</div>
        ) : (
            <div className="flex gap-2">
                {hasProfileResume && <button type="button" onClick={() => onTriggerAutofill(true)} className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-semibold hover:bg-indigo-700">From Profile</button>}
                {hasUploadedResume && <button type="button" onClick={() => onTriggerAutofill(false)} className="px-3 py-1.5 bg-white border border-indigo-200 text-indigo-700 rounded-lg text-xs font-semibold hover:bg-indigo-50">From Upload</button>}
            </div>
        )}
    </div>
);

const ResumeUploadSection = ({ resumeFile, onFileSelect, profileResumeUrl, onPreview }) => {
    const fileRef = useRef(null);
    return (
        <div className="space-y-2">
            <label className="block text-sm font-semibold text-gray-700">Resume Document <span className="text-red-500">*</span></label>
            <div className="border-2 border-dashed border-gray-300 rounded-xl p-4 text-center cursor-pointer hover:bg-gray-50" onClick={() => fileRef.current?.click()}>
                <input ref={fileRef} type="file" accept=".pdf,.doc,.docx" onChange={(e) => onFileSelect(e.target.files?.[0])} className="hidden" />
                <p className="text-sm font-medium text-gray-700">{resumeFile ? resumeFile.name : (profileResumeUrl ? "Using Profile Resume (Click to replace)" : "Click to upload resume (PDF, DOC, DOCX)")}</p>
                {profileResumeUrl && !resumeFile && <button type="button" onClick={(e) => { e.stopPropagation(); onPreview(); }} className="mt-1 text-xs text-primary-600 underline">Preview Saved Resume</button>}
            </div>
        </div>
    );
};

const INITIAL_FORM = {
    full_name: '',
    email: '',
    phone_number: '',
    university_name: '',
    university_country: '',
    academic_level: 'Bachelor',
    stream: '',
    current_year: '',
    graduation_year: new Date().getFullYear(),
    major: '',
    minor: '',
    grading_system: 'GPA',
    overall_grade: '',
    skills: '',
    area_of_interest: '',
    linkedin_profile: '',
    github_profile: '',
    referral_source: '',
    work_authorization_country: '',
    cover_letter: ''
};

const REQUIRED_FIELDS = [
    'full_name', 'email', 'phone_number', 'university_name', 'university_country',
    'stream', 'current_year', 'graduation_year', 'major', 'grading_system',
    'overall_grade', 'skills', 'area_of_interest', 'linkedin_profile', 'referral_source', 'work_authorization_country'
];

const ApplicationModal = ({ isOpen, onClose, job, user, onApplySuccess }) => {
    const [resumeFile, setResumeFile] = useState(null);
    const [formErrors, setFormErrors] = useState({});
    const [formData, setFormData] = useState({
        ...INITIAL_FORM,
        full_name: user?.username || '',
        email: user?.email || ''
    });

    const [applying, setApplying] = useState(false);
    const [error, setError] = useState('');
    const [autofilling, setAutofilling] = useState(false);
    const [autofillSuccess, setAutofillSuccess] = useState(false);
    const [conflicts, setConflicts] = useState({});

    const [previewTarget, setPreviewTarget] = useState(null);
    const [previewName, setPreviewName] = useState('');
    const [isPreviewOpen, setIsPreviewOpen] = useState(false);

    useEffect(() => {
        if (!isOpen) return;
        setFormData(prev => ({
            ...prev,
            full_name: user?.username || prev.full_name,
            email: user?.email || prev.email
        }));
    }, [isOpen, user]);

    const handlePreview = (target, name) => {
        setPreviewTarget(target);
        setPreviewName(name || (target instanceof File ? target.name : 'Resume'));
        setIsPreviewOpen(true);
    };

    const handleAutofill = async (useProfile = false) => {
        setAutofilling(true);
        setError('');
        try {
            let res;
            if (useProfile) {
                res = await api.post('/applications/autofill/', { use_profile_resume: true });
            } else if (resumeFile) {
                const fd = new FormData();
                fd.append('resume', resumeFile);
                res = await api.post('/applications/autofill/', fd, {
                    headers: { 'Content-Type': undefined }
                });
            } else {
                return;
            }

            const { mapped_form_data, conflicts: resConflicts } = res.data;
            if (mapped_form_data) {
                setFormData(prev => ({ ...prev, ...mapped_form_data }));
                setConflicts(resConflicts || {});
                setAutofillSuccess(true);
            }
        } catch (err) {
            setError(err.response?.data?.detail || 'Autofill could not parse this resume file. Please fill in the fields manually.');
        } finally {
            setAutofilling(false);
        }
    };

    const handleApplyConflict = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
        setConflicts(prev => {
            const next = { ...prev };
            delete next[field];
            return next;
        });
    };

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
        setFormErrors(prev => ({ ...prev, [name]: '' }));
        setError('');
    };

    const validateForm = () => {
        const errors = {};
        REQUIRED_FIELDS.forEach((f) => {
            if (!String(formData[f] || '').trim()) {
                errors[f] = 'This field is required.';
            }
        });

        if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
            errors.email = 'Please enter a valid email address.';
        }
        if (formData.phone_number && !/^\+?[0-9\s-]{7,15}$/.test(formData.phone_number)) {
            errors.phone_number = 'Please enter a valid phone number.';
        }
        if (formData.linkedin_profile && !/^https?:\/\//i.test(formData.linkedin_profile)) {
            errors.linkedin_profile = 'Please enter a valid URL.';
        }
        if (formData.github_profile && !/^https?:\/\//i.test(formData.github_profile)) {
            errors.github_profile = 'Please enter a valid URL.';
        }
        return errors;
    };

    const handleApply = async () => {
        setApplying(true);
        setError('');
        const vErrors = validateForm();
        setFormErrors(vErrors);

        if (Object.keys(vErrors).length > 0) {
            setError(Object.values(vErrors)[0] || 'Please fill in all required fields correctly.');
            setApplying(false);
            return;
        }

        try {
            if (!resumeFile && !user?.candidate_profile?.resume) {
                setError('Please upload a resume');
                setApplying(false);
                return;
            }

            const form = new FormData();
            form.append('job', job.id);
            Object.keys(formData).forEach(key => {
                if (formData[key] !== '') form.append(key, formData[key]);
            });
            if (resumeFile) form.append('resume_snapshot', resumeFile);

            await api.post('/applications/', form, {
                headers: { 'Content-Type': undefined }
            });
            onApplySuccess();
            onClose();
        } catch (err) {
            setError(err.response?.data?.resume_snapshot?.[0] || err.response?.data?.non_field_errors?.[0] || Object.values(err.response?.data || {})?.[0]?.[0] || 'Failed to apply.');
        } finally {
            setApplying(false);
        }
    };

    if (!isOpen) return null;

    return createPortal(
        <>
            <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 animate-fade-in">
                <div className="absolute inset-0 bg-black/50 backdrop-blur-xs" onClick={onClose} aria-hidden="true" />
                <div className="relative bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-gray-100" role="dialog" aria-modal="true">
                    <div className="shrink-0 bg-primary-600 text-white p-6 flex items-center justify-between">
                        <div>
                            <h2 className="text-2xl font-bold">Apply for {job?.title}</h2>
                            <p className="text-xs text-primary-100 mt-0.5">{job?.category} • {job?.location || 'Remote'}</p>
                        </div>
                        <button onClick={onClose} className="hover:bg-primary-700 p-2 rounded-lg transition-colors">
                            <X className="w-6 h-6" />
                        </button>
                    </div>

                    <div className="flex-1 min-h-0 overflow-y-auto p-6 sm:p-8 space-y-6">
                        {error && (
                            <div className="bg-red-50 text-red-700 p-4 rounded-xl flex items-center gap-2 border border-red-200">
                                <AlertCircle className="w-5 h-5 shrink-0" />
                                <span>{error}</span>
                            </div>
                        )}

                        <AutofillBanner
                            hasProfileResume={Boolean(user?.candidate_profile?.resume)}
                            hasUploadedResume={Boolean(resumeFile)}
                            onTriggerAutofill={handleAutofill}
                            autofilling={autofilling}
                            autofillSuccess={autofillSuccess}
                            conflicts={conflicts}
                            onApplyConflictResolution={handleApplyConflict}
                        />

                        <ResumeUploadSection
                            resumeFile={resumeFile}
                            onFileSelect={setResumeFile}
                            profileResumeUrl={user?.candidate_profile?.resume}
                            onPreview={handlePreview}
                        />

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">Full Name *</label>
                                <input type="text" name="full_name" value={formData.full_name} onChange={handleInputChange} required className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">Email *</label>
                                <input type="email" name="email" value={formData.email} onChange={handleInputChange} required className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">Phone Number *</label>
                                <input type="tel" name="phone_number" value={formData.phone_number} onChange={handleInputChange} required className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">University Name *</label>
                                <input type="text" name="university_name" value={formData.university_name} onChange={handleInputChange} required className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">University Country *</label>
                                <input type="text" name="university_country" value={formData.university_country} onChange={handleInputChange} required className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">Academic Level *</label>
                                <select name="academic_level" value={formData.academic_level} onChange={handleInputChange} className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500">
                                    <option>Bachelor</option><option>Master</option><option>PhD</option><option>Diploma</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">Stream *</label>
                                <input type="text" name="stream" value={formData.stream} onChange={handleInputChange} placeholder="e.g., Engineering, Arts" required className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">Current Year *</label>
                                <input type="text" name="current_year" value={formData.current_year} onChange={handleInputChange} placeholder="e.g., 3rd, 4th" required className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">Graduation Year *</label>
                                <input type="number" name="graduation_year" value={formData.graduation_year} onChange={handleInputChange} required className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">Major *</label>
                                <input type="text" name="major" value={formData.major} onChange={handleInputChange} required className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">Minor</label>
                                <input type="text" name="minor" value={formData.minor} onChange={handleInputChange} className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">Grading System *</label>
                                <select name="grading_system" value={formData.grading_system} onChange={handleInputChange} className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500">
                                    <option>GPA</option><option>CGPA</option><option>Percentage</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">Overall Grade *</label>
                                <input type="text" name="overall_grade" value={formData.overall_grade} onChange={handleInputChange} required className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">Area of Interest *</label>
                                <input type="text" name="area_of_interest" value={formData.area_of_interest} onChange={handleInputChange} required className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">LinkedIn Profile *</label>
                                <input type="url" name="linkedin_profile" value={formData.linkedin_profile} onChange={handleInputChange} placeholder="https://linkedin.com/in/..." required className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 ${formErrors.linkedin_profile ? 'border-red-400' : 'border-gray-300'}`} />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">GitHub Profile</label>
                                <input type="url" name="github_profile" value={formData.github_profile} onChange={handleInputChange} placeholder="https://github.com/..." className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 ${formErrors.github_profile ? 'border-red-400' : 'border-gray-300'}`} />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">Referral Source *</label>
                                <input type="text" name="referral_source" value={formData.referral_source} onChange={handleInputChange} placeholder="e.g., LinkedIn, Friend" required className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">Work Authorization Country *</label>
                                <input type="text" name="work_authorization_country" value={formData.work_authorization_country} onChange={handleInputChange} required className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-semibold text-gray-700 mb-2">Skills *</label>
                            <textarea name="skills" value={formData.skills} onChange={handleInputChange} placeholder="e.g., Python, React, Django" required rows={3} className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
                        </div>

                        <div>
                            <label className="block text-sm font-semibold text-gray-700 mb-2">Cover Letter</label>
                            <textarea name="cover_letter" value={formData.cover_letter} onChange={handleInputChange} placeholder="Tell us why you're a great fit for this role" rows={4} className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
                        </div>
                    </div>

                    <div className="shrink-0 flex gap-4 p-6 border-t bg-white">
                        <button type="button" onClick={onClose} disabled={applying} className="flex-1 px-6 py-3 border border-gray-300 rounded-lg font-semibold text-gray-700 hover:bg-gray-50 transition-colors">
                            Cancel
                        </button>
                        <button type="button" onClick={handleApply} disabled={applying || (!resumeFile && !user?.candidate_profile?.resume)} className="flex-1 px-6 py-3 bg-primary-600 text-white rounded-lg font-semibold hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2">
                            {applying ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                            {applying ? 'Submitting...' : 'Submit Application'}
                        </button>
                    </div>
                </div>
            </div>

            <ResumePreviewModal
                isOpen={isPreviewOpen}
                onClose={() => setIsPreviewOpen(false)}
                file={previewTarget}
                fileName={previewName}
            />
        </>,
        document.body
    );
};

export default ApplicationModal;
