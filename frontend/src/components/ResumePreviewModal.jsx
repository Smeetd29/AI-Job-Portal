import { useState, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { X, ExternalLink, Download, FileText, Loader2 } from 'lucide-react';
import api from '../axios';

const formatSize = (b) => !b ? '' : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(2)} MB`;

const resolveUrl = (f) => {
    if (!f) return null;
    if (f instanceof Blob || f instanceof File) return URL.createObjectURL(f);
    if (typeof f === 'string') {
        if (f.startsWith('http://') || f.startsWith('https://') || f.startsWith('blob:')) return f;
        return `${(api.defaults.baseURL || window.location.origin).replace(/\/$/, '')}/${f.replace(/^\//, '')}`;
    }
    return null;
};

const ResumePreviewModal = ({ isOpen, onClose, file, fileName: fallbackName }) => {
    const [loading, setLoading] = useState(true);
    const [previewUrl, setPreviewUrl] = useState(null);

    const { name, isPdf, isDoc, size } = useMemo(() => {
        const isFile = file instanceof Blob || file instanceof File;
        const n = (isFile ? file.name : (typeof file === 'string' ? file.split('?')[0].split('/').pop() : '')) || fallbackName || 'Resume';
        const ext = (n.split('.').pop() || '').toLowerCase();
        return { name: n, isPdf: ext === 'pdf' || file?.type === 'application/pdf', isDoc: ['doc', 'docx'].includes(ext) || file?.type?.includes('word'), size: isFile ? file.size : null };
    }, [file, fallbackName]);

    useEffect(() => {
        if (!isOpen || !file) { setPreviewUrl(null); return; }
        const url = resolveUrl(file);
        setPreviewUrl(url);
        setLoading(true);
        return () => { if (url && (file instanceof Blob || file instanceof File)) URL.revokeObjectURL(url); };
    }, [isOpen, file]);

    useEffect(() => {
        if (!isOpen) return;
        const onKey = (e) => e.key === 'Escape' && onClose();
        const prev = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        window.addEventListener('keydown', onKey);
        return () => { document.body.style.overflow = prev; window.removeEventListener('keydown', onKey); };
    }, [isOpen, onClose]);

    if (!isOpen || !file) return null;

    return createPortal(
        <div className="fixed inset-0 z-[150] flex items-center justify-center p-2 sm:p-4 md:p-6 animate-fade-in">
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
            <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-5xl h-[92vh] flex flex-col overflow-hidden border border-gray-100" role="dialog">
                <div className="shrink-0 bg-gray-900 text-white px-6 py-4 flex items-center justify-between border-b border-gray-800">
                    <div className="flex items-center gap-3 min-w-0">
                        <div className={`p-2 rounded-lg ${isPdf ? 'bg-red-500/20 text-red-400' : 'bg-blue-500/20 text-blue-400'}`}>
                            <FileText className="w-5 h-5 shrink-0" />
                        </div>
                        <div className="min-w-0">
                            <div className="flex items-center gap-2">
                                <h3 className="font-semibold text-base sm:text-lg truncate">{name}</h3>
                                <span className={`text-[11px] font-bold px-2 py-0.5 rounded uppercase ${isPdf ? 'bg-red-500/30 text-red-300' : 'bg-blue-500/30 text-blue-300'}`}>
                                    {isPdf ? 'PDF' : isDoc ? 'DOCX' : 'DOC'}
                                </span>
                            </div>
                            {size && <p className="text-xs text-gray-400">{formatSize(size)}</p>}
                        </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                        {previewUrl && (
                            <>
                                <a href={previewUrl} target="_blank" rel="noreferrer" className="p-2 text-gray-300 hover:text-white hover:bg-gray-800 rounded-lg flex items-center gap-1.5 text-xs font-medium">
                                    <ExternalLink className="w-4 h-4" /> <span className="hidden sm:inline">Open in New Tab</span>
                                </a>
                                <a href={previewUrl} download={name} className="p-2 text-gray-300 hover:text-white hover:bg-gray-800 rounded-lg flex items-center gap-1.5 text-xs font-medium">
                                    <Download className="w-4 h-4" /> <span className="hidden sm:inline">Download</span>
                                </a>
                            </>
                        )}
                        <button type="button" onClick={onClose} className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg ml-1">
                            <X className="w-5 h-5" />
                        </button>
                    </div>
                </div>

                <div className="flex-1 bg-gray-100 relative overflow-hidden">
                    {isPdf && previewUrl ? (
                        <>
                            {loading && (
                                <div className="absolute inset-0 flex items-center justify-center bg-gray-50/80 z-10">
                                    <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
                                </div>
                            )}
                            <iframe src={previewUrl} title={name} className="w-full h-full border-0" onLoad={() => setLoading(false)} />
                        </>
                    ) : (
                        <div className="h-full flex flex-col items-center justify-center p-8 text-center bg-gray-50">
                            <FileText className="w-12 h-12 text-blue-600 mb-3" />
                            <h4 className="text-lg font-bold text-gray-900 mb-1">{name}</h4>
                            {size && <p className="text-xs text-gray-500 mb-4">{formatSize(size)}</p>}
                            <p className="text-xs text-gray-500 max-w-sm mb-4">Preview not available directly in browser for this format. Download to view.</p>
                            {previewUrl && (
                                <a href={previewUrl} download={name} className="btn btn-primary flex items-center gap-2 px-5 py-2.5 rounded-xl shadow">
                                    <Download className="w-4 h-4" /> Download Document
                                </a>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>,
        document.body
    );
};

export default ResumePreviewModal;
