import { useState, useEffect } from 'react';
import api from '../../axios';
import { 
    Sparkles, 
    Check, 
    X, 
    Edit3, 
    Play, 
    Settings, 
    RefreshCw, 
    ShieldCheck, 
    AlertCircle, 
    Clock, 
    Briefcase, 
    ChevronRight, 
    Loader2,
    Sliders,
    Building2,
    Send
} from 'lucide-react';
import { Link } from 'react-router-dom';

const AutoApplyPage = () => {
    const [pendingActions, setPendingActions] = useState([]);
    const [settingsData, setSettingsData] = useState({
        enabled: false,
        min_score_threshold: 85,
        mode: 'review_first',
        daily_cap: 3,
        excluded_companies: []
    });
    const [loading, setLoading] = useState(true);
    const [running, setRunning] = useState(false);
    const [runMessage, setRunMessage] = useState(null);
    const [actionLoading, setActionLoading] = useState({});
    const [editingAction, setEditingAction] = useState(null);
    const [editedCoverLetter, setEditedCoverLetter] = useState('');
    const [showSettingsModal, setShowSettingsModal] = useState(false);
    const [settingsSaving, setSettingsSaving] = useState(false);

    const fetchData = async () => {
        setLoading(true);
        try {
            const [pendingRes, settingsRes] = await Promise.all([
                api.get('/api/auto-apply/pending/'),
                api.get('/api/auto-apply/settings/')
            ]);
            setPendingActions(pendingRes.data || []);
            setSettingsData(settingsRes.data || {});
        } catch (error) {
            console.error('Failed to load auto-apply data', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const handleRunNow = async () => {
        setRunning(true);
        setRunMessage(null);
        try {
            const res = await api.post('/api/auto-apply/run-now/');
            if (res.data.skipped) {
                setRunMessage({ type: 'warning', text: res.data.message || 'Run skipped (check caps or enabled status).' });
            } else {
                setRunMessage({ 
                    type: 'success', 
                    text: `Agent finished! Qualified ${res.data.qualified_count || 0} jobs. Found ${res.data.actions_created || 0} applications to review.` 
                });
            }
            await fetchData();
        } catch (error) {
            setRunMessage({ type: 'error', text: error.response?.data?.error || 'Failed to execute auto-apply run.' });
        } finally {
            setRunning(false);
        }
    };

    const handleApprove = async (actionId) => {
        setActionLoading(prev => ({ ...prev, [actionId]: 'approving' }));
        try {
            await api.post(`/api/auto-apply/${actionId}/approve/`);
            setPendingActions(prev => prev.filter(a => a.action_id !== actionId));
        } catch (error) {
            alert(error.response?.data?.error || 'Failed to approve application.');
        } finally {
            setActionLoading(prev => ({ ...prev, [actionId]: null }));
        }
    };

    const handleReject = async (actionId) => {
        setActionLoading(prev => ({ ...prev, [actionId]: 'rejecting' }));
        try {
            await api.post(`/api/auto-apply/${actionId}/reject/`);
            setPendingActions(prev => prev.filter(a => a.action_id !== actionId));
        } catch (error) {
            alert(error.response?.data?.error || 'Failed to reject action.');
        } finally {
            setActionLoading(prev => ({ ...prev, [actionId]: null }));
        }
    };

    const handleEditAndApprove = async () => {
        if (!editingAction) return;
        const actionId = editingAction.action_id;
        setActionLoading(prev => ({ ...prev, [actionId]: 'saving_edit' }));
        try {
            await api.post(`/api/auto-apply/${actionId}/edit-and-approve/`, {
                cover_letter: editedCoverLetter
            });
            setPendingActions(prev => prev.filter(a => a.action_id !== actionId));
            setEditingAction(null);
        } catch (error) {
            alert(error.response?.data?.error || 'Failed to submit edited application.');
        } finally {
            setActionLoading(prev => ({ ...prev, [actionId]: null }));
        }
    };

    const handleSaveSettings = async () => {
        setSettingsSaving(true);
        try {
            const res = await api.put('/api/auto-apply/settings/', settingsData);
            setSettingsData(res.data);
            setShowSettingsModal(false);
        } catch (error) {
            alert('Failed to save settings.');
        } finally {
            setSettingsSaving(false);
        }
    };

    return (
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-in">
            {/* Header Banner */}
            <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-6 sm:p-8 text-white shadow-xl relative overflow-hidden border border-slate-800">
                <div className="absolute right-0 top-0 translate-x-12 -translate-y-12 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
                <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
                    <div className="space-y-2">
                        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                            <Sparkles className="w-3.5 h-3.5" />
                            Autonomous Career Co-Pilot
                        </div>
                        <h1 className="text-3xl font-black tracking-tight">Auto-Apply Approval Queue</h1>
                        <p className="text-slate-300 text-sm max-w-xl">
                            The agent evaluates job recommendations against your preferences, crafts tailored cover letters, and awaits your single-tap approval.
                        </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                        <button
                            onClick={() => setShowSettingsModal(true)}
                            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold bg-white/10 hover:bg-white/20 text-white border border-white/10 transition-all backdrop-blur"
                        >
                            <Settings className="w-4 h-4" />
                            Settings & Guardrails
                        </button>
                        <button
                            onClick={handleRunNow}
                            disabled={running}
                            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white shadow-lg shadow-cyan-500/20 transition-all disabled:opacity-50"
                        >
                            {running ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Agent Searching...
                                </>
                            ) : (
                                <>
                                    <Play className="w-4 h-4 fill-white" />
                                    Run Agent Now
                                </>
                            )}
                        </button>
                    </div>
                </div>

                {/* Status Badges */}
                <div className="mt-6 pt-6 border-t border-slate-800/80 flex flex-wrap items-center gap-6 text-xs">
                    <div className="flex items-center gap-2">
                        <div className={`w-2.5 h-2.5 rounded-full ${settingsData.enabled ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
                        <span className="text-slate-300">Agent Status:</span>
                        <span className="font-bold text-white">{settingsData.enabled ? 'Active' : 'Paused'}</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4 text-cyan-400" />
                        <span className="text-slate-300">Guardrail Mode:</span>
                        <span className="font-bold text-white capitalize">{settingsData.mode?.replace('_', ' ')}</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <Sliders className="w-4 h-4 text-indigo-400" />
                        <span className="text-slate-300">Min Score:</span>
                        <span className="font-bold text-white">{settingsData.min_score_threshold}%</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <Clock className="w-4 h-4 text-amber-400" />
                        <span className="text-slate-300">Daily Cap:</span>
                        <span className="font-bold text-white">{settingsData.daily_cap} applications/day</span>
                    </div>
                </div>
            </div>

            {/* Run Feedback Alert */}
            {runMessage && (
                <div className={`p-4 rounded-2xl flex items-center gap-3 text-sm font-medium ${
                    runMessage.type === 'success' ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' :
                    runMessage.type === 'warning' ? 'bg-amber-50 text-amber-800 border border-amber-200' :
                    'bg-red-50 text-red-800 border border-red-200'
                }`}>
                    <AlertCircle className="w-5 h-5 shrink-0" />
                    <span>{runMessage.text}</span>
                </div>
            )}

            {/* Main Content: Pending Applications */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                        Pending Approvals
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                            {pendingActions.length}
                        </span>
                    </h2>
                    <button
                        onClick={fetchData}
                        className="text-xs font-semibold text-slate-500 hover:text-cyan-600 flex items-center gap-1.5 transition-colors"
                    >
                        <RefreshCw className="w-3.5 h-3.5" />
                        Refresh Queue
                    </button>
                </div>

                {loading ? (
                    <div className="py-20 flex flex-col items-center justify-center gap-3">
                        <Loader2 className="w-8 h-8 animate-spin text-cyan-600" />
                        <p className="text-sm font-medium text-slate-500">Loading pending auto-apply actions...</p>
                    </div>
                ) : pendingActions.length === 0 ? (
                    <div className="bg-white rounded-3xl border border-slate-200/80 p-12 text-center shadow-sm space-y-4">
                        <div className="w-16 h-16 rounded-2xl bg-cyan-50 text-cyan-600 flex items-center justify-center mx-auto">
                            <ShieldCheck className="w-8 h-8" />
                        </div>
                        <h3 className="text-lg font-bold text-slate-900">Queue is clear!</h3>
                        <p className="text-slate-500 text-sm max-w-md mx-auto">
                            There are currently no applications awaiting review. You can trigger the agent now to scan fresh job openings against your profile.
                        </p>
                        <button
                            onClick={handleRunNow}
                            disabled={running}
                            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold bg-slate-900 hover:bg-slate-800 text-white transition-all"
                        >
                            <Play className="w-4 h-4 fill-white" />
                            Run Search Agent
                        </button>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {pendingActions.map((action) => (
                            <div 
                                key={action.action_id} 
                                className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm hover:shadow-md transition-all flex flex-col lg:flex-row lg:items-start justify-between gap-6"
                            >
                                <div className="space-y-3 flex-1 min-w-0">
                                    <div className="flex flex-wrap items-center gap-3">
                                        <Link 
                                            to={action.job_id ? `/jobs/${action.job_id}` : '#'} 
                                            className="text-lg font-bold text-slate-900 hover:text-cyan-600 transition-colors"
                                        >
                                            {action.job_title || 'Software Engineering Role'}
                                        </Link>
                                        <div className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full text-xs font-black bg-emerald-50 text-emerald-700 border border-emerald-200">
                                            {action.score}% Match
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-3 text-sm text-slate-500">
                                        <span className="flex items-center gap-1.5 font-semibold text-slate-700">
                                            <Building2 className="w-4 h-4 text-slate-400" />
                                            {action.company_name || 'Hiring Company'}
                                        </span>
                                        <span>•</span>
                                        <span>{new Date(action.created_at).toLocaleDateString()}</span>
                                    </div>

                                    {/* Cover Letter Accordion/Preview */}
                                    <div className="bg-slate-50 rounded-xl p-4 border border-slate-200/60 text-xs text-slate-700 space-y-1.5">
                                        <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-wider text-slate-400">
                                            <span>AI-Tailored Cover Letter</span>
                                            <button 
                                                onClick={() => {
                                                    setEditingAction(action);
                                                    setEditedCoverLetter(action.cover_letter || '');
                                                }}
                                                className="text-cyan-700 hover:text-cyan-800 flex items-center gap-1 capitalize"
                                            >
                                                <Edit3 className="w-3 h-3" /> Edit Note
                                            </button>
                                        </div>
                                        <p className="line-clamp-3 whitespace-pre-line leading-relaxed italic">
                                            "{action.cover_letter}"
                                        </p>
                                    </div>
                                </div>

                                {/* Actions */}
                                <div className="flex sm:flex-row lg:flex-col items-center gap-2 shrink-0">
                                    <button
                                        onClick={() => handleApprove(action.action_id)}
                                        disabled={actionLoading[action.action_id] === 'approving'}
                                        className="w-full sm:w-auto px-5 py-2.5 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm flex items-center justify-center gap-1.5 transition-all"
                                    >
                                        {actionLoading[action.action_id] === 'approving' ? (
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                        ) : (
                                            <>
                                                <Check className="w-4 h-4" />
                                                Approve & Apply
                                            </>
                                        )}
                                    </button>

                                    <button
                                        onClick={() => {
                                            setEditingAction(action);
                                            setEditedCoverLetter(action.cover_letter || '');
                                        }}
                                        className="w-full sm:w-auto px-4 py-2.5 rounded-xl text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 flex items-center justify-center gap-1.5 transition-all"
                                    >
                                        <Edit3 className="w-3.5 h-3.5" />
                                        Edit
                                    </button>

                                    <button
                                        onClick={() => handleReject(action.action_id)}
                                        disabled={actionLoading[action.action_id] === 'rejecting'}
                                        className="w-full sm:w-auto px-4 py-2.5 rounded-xl text-xs font-bold text-red-600 hover:bg-red-50 flex items-center justify-center gap-1.5 transition-all"
                                    >
                                        {actionLoading[action.action_id] === 'rejecting' ? (
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                        ) : (
                                            <>
                                                <X className="w-3.5 h-3.5" />
                                                Reject
                                            </>
                                        )}
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Edit Cover Letter Modal */}
            {editingAction && (
                <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="bg-white rounded-3xl max-w-2xl w-full p-6 sm:p-8 space-y-6 shadow-2xl animate-scale-up">
                        <div className="flex items-center justify-between border-b pb-4">
                            <div>
                                <h3 className="text-lg font-bold text-slate-900">Edit Application Pitch</h3>
                                <p className="text-xs text-slate-500">{editingAction.job_title} @ {editingAction.company_name}</p>
                            </div>
                            <button onClick={() => setEditingAction(null)} className="p-2 text-slate-400 hover:text-slate-600 rounded-lg">
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-700 uppercase">Cover Letter / Note</label>
                            <textarea
                                rows={8}
                                value={editedCoverLetter}
                                onChange={(e) => setEditedCoverLetter(e.target.value)}
                                className="w-full p-4 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-cyan-500 focus:outline-none"
                                placeholder="Refine your cover note before submitting..."
                            />
                        </div>

                        <div className="flex justify-end gap-3 pt-2">
                            <button
                                onClick={() => setEditingAction(null)}
                                className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleEditAndApprove}
                                disabled={actionLoading[editingAction.action_id] === 'saving_edit'}
                                className="px-5 py-2 rounded-xl text-xs font-bold bg-cyan-600 hover:bg-cyan-500 text-white flex items-center gap-1.5"
                            >
                                {actionLoading[editingAction.action_id] === 'saving_edit' ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    <>
                                        <Send className="w-4 h-4" />
                                        Save & Approve
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Settings Modal */}
            {showSettingsModal && (
                <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-8 space-y-6 shadow-2xl animate-scale-up">
                        <div className="flex items-center justify-between border-b pb-4">
                            <div className="flex items-center gap-2">
                                <Settings className="w-5 h-5 text-indigo-600" />
                                <h3 className="text-lg font-bold text-slate-900">Auto-Apply Guardrails</h3>
                            </div>
                            <button onClick={() => setShowSettingsModal(false)} className="p-2 text-slate-400 hover:text-slate-600 rounded-lg">
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-2xl">
                                <div>
                                    <h4 className="text-sm font-bold text-slate-900">Enable Agent</h4>
                                    <p className="text-xs text-slate-500">Allow agent to search and queue recommendations</p>
                                </div>
                                <input
                                    type="checkbox"
                                    checked={settingsData.enabled}
                                    onChange={(e) => setSettingsData(prev => ({ ...prev, enabled: e.target.checked }))}
                                    className="w-5 h-5 text-cyan-600 rounded focus:ring-cyan-500"
                                />
                            </div>

                            <div className="space-y-1.5">
                                <div className="flex justify-between text-xs font-bold text-slate-700">
                                    <span>Minimum Match Score Threshold</span>
                                    <span>{settingsData.min_score_threshold}%</span>
                                </div>
                                <input
                                    type="range"
                                    min="30"
                                    max="95"
                                    step="5"
                                    value={settingsData.min_score_threshold}
                                    onChange={(e) => setSettingsData(prev => ({ ...prev, min_score_threshold: parseInt(e.target.value) }))}
                                    className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-cyan-600"
                                />
                            </div>

                            <div className="space-y-1.5">
                                <label className="text-xs font-bold text-slate-700">Daily Application Quota</label>
                                <input
                                    type="number"
                                    min="1"
                                    max="20"
                                    value={settingsData.daily_cap}
                                    onChange={(e) => setSettingsData(prev => ({ ...prev, daily_cap: parseInt(e.target.value) }))}
                                    className="w-full p-3 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-cyan-500 focus:outline-none"
                                />
                            </div>

                            <div className="space-y-1.5">
                                <label className="text-xs font-bold text-slate-700">Operation Mode</label>
                                <select
                                    value={settingsData.mode}
                                    onChange={(e) => setSettingsData(prev => ({ ...prev, mode: e.target.value }))}
                                    className="w-full p-3 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-cyan-500 focus:outline-none bg-white"
                                >
                                    <option value="review_first">Review First (Human in the loop - Recommended)</option>
                                    <option value="auto_submit">Auto Submit (Instant apply on match)</option>
                                </select>
                            </div>
                        </div>

                        <div className="flex justify-end gap-3 pt-4 border-t">
                            <button
                                onClick={() => setShowSettingsModal(false)}
                                className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleSaveSettings}
                                disabled={settingsSaving}
                                className="px-5 py-2 rounded-xl text-xs font-bold bg-slate-900 hover:bg-slate-800 text-white flex items-center gap-1.5"
                            >
                                {settingsSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save Guardrails'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default AutoApplyPage;
