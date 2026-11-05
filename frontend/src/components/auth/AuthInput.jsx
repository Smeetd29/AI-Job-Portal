import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

const AuthInput = ({
    id,
    name,
    label,
    type = 'text',
    required = false,
    value,
    onChange,
    disabled = false,
    placeholder = '',
    icon: Icon,
    rightAction = null,
    autoComplete,
    compact = false,
}) => {
    const [showPassword, setShowPassword] = useState(false);
    const isPassword = type === 'password';
    const computedType = isPassword ? (showPassword ? 'text' : 'password') : type;

    return (
        <div className={compact ? "space-y-1" : "space-y-1.5"}>
            <div className="flex items-center justify-between">
                <label 
                    htmlFor={id} 
                    className="block text-[11px] font-bold text-slate-700 tracking-wide uppercase"
                >
                    {label} {required && <span className="text-rose-500 font-bold">*</span>}
                </label>
                {rightAction}
            </div>

            <div className={`relative flex items-center ${compact ? 'h-10' : 'h-11'} w-full rounded-xl border border-slate-200 bg-slate-50/70 hover:bg-slate-50/90 focus-within:bg-white focus-within:border-blue-600 focus-within:ring-2 focus-within:ring-blue-500/20 transition-all duration-200 overflow-hidden shadow-sm`}>
                {Icon && (
                    <div className="pl-3.5 pr-2.5 flex items-center justify-center text-slate-400 shrink-0 select-none">
                        <Icon className="w-4 h-4 text-slate-400" />
                    </div>
                )}

                <input
                    id={id}
                    name={name || id}
                    type={computedType}
                    required={required}
                    value={value}
                    onChange={onChange}
                    disabled={disabled}
                    placeholder={placeholder}
                    autoComplete={autoComplete}
                    className="w-full h-full bg-transparent px-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                />

                {isPassword && (
                    <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="px-3.5 h-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors focus:outline-none"
                        tabIndex={-1}
                        title={showPassword ? 'Hide password' : 'Show password'}
                    >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                )}
            </div>
        </div>
    );
};

export default AuthInput;
