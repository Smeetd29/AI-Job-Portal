import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

const SLIDES = [
    {
        id: 1,
        image: '/images/landing-hero.jpg',
        title: 'Intelligent AI Matching',
        subtitle: 'Deterministic skill analysis & ML match scoring',
        alt: 'Intelligent AI Resume Matching',
    },
    {
        id: 2,
        image: '/images/career-success.jpg',
        title: 'Accelerate Career Growth',
        subtitle: 'Connect with verified opportunities tailored for you',
        alt: 'Accelerate Career Growth',
    },
    {
        id: 3,
        image: '/images/recruitment-checklist.jpg',
        title: 'Seamless Application Pipeline',
        subtitle: 'Track your hiring journey with total transparency',
        alt: 'Seamless Application Workflows',
    },
];

const EXTENDED_SLIDES = [SLIDES[SLIDES.length - 1], ...SLIDES, SLIDES[0]];

const LandingPage = () => {
    const [currentSlide, setCurrentSlide] = useState(1);
    const [isTransitioning, setIsTransitioning] = useState(true);
    const [isHovered, setIsHovered] = useState(false);

    useEffect(() => {
        document.title = 'CareerConnect — Launch Your Next Career Move';
    }, []);

    useEffect(() => {
        if (isHovered) return;
        const timer = setInterval(() => {
            setIsTransitioning(true);
            setCurrentSlide((prev) => prev + 1);
        }, 4000);
        return () => clearInterval(timer);
    }, [isHovered]);

    const handleTransitionEnd = () => {
        if (currentSlide >= SLIDES.length + 1) {
            setIsTransitioning(false);
            setCurrentSlide(1);
        } else if (currentSlide <= 0) {
            setIsTransitioning(false);
            setCurrentSlide(SLIDES.length);
        }
    };

    const handleDotClick = (idx) => {
        setIsTransitioning(true);
        setCurrentSlide(idx + 1);
    };

    const activeIndex = (currentSlide - 1 + SLIDES.length) % SLIDES.length;

    return (
        <div className="w-full h-full flex-1 flex flex-col lg:flex-row text-slate-900 selection:bg-cyan-100 selection:text-cyan-900 overflow-y-auto lg:overflow-hidden">
            {/* PART 1: FULL WHITE (LEFT SIDE) */}
            <div className="w-full lg:w-1/2 bg-white flex flex-col justify-between px-6 sm:px-12 lg:px-14 xl:px-20 py-8 lg:py-12 text-left z-10 shrink-0 lg:shrink min-h-full">
                {/* Brand Logo Header */}
                <div className="flex items-center gap-2.5">
                    <img 
                        src="/images/career-connect-logo.png" 
                        alt="Career Connect" 
                        className="w-10 h-10 object-contain hover:scale-105 transition-transform duration-200"
                    />
                    <span className="text-2xl font-black tracking-tight text-slate-900">
                        Career<span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-600 to-blue-600">Connect</span>
                    </span>
                </div>

                <div className="max-w-xl space-y-6 mx-auto lg:mx-0 w-full my-auto py-8">
                    <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-cyan-50 border border-cyan-200/80 text-cyan-800 text-xs sm:text-sm font-semibold tracking-wide">
                        <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse"></span>
                        Next-Gen AI Career Ecosystem
                    </div>

                    <h1 className="text-4xl sm:text-5xl xl:text-6xl font-black text-slate-900 tracking-tight leading-[1.1]">
                        Launch Your Next{' '}
                        <span className="bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-600 bg-clip-text text-transparent">
                            Career Move
                        </span>
                    </h1>

                    <p className="text-base sm:text-lg text-slate-600 leading-relaxed">
                        Intelligent resume-job matching and seamless application workflows. Connect with high-impact opportunities powered by real-time ML scoring and deterministic evidence.
                    </p>

                    <div className="flex flex-wrap items-center gap-4 pt-2">
                        <Link
                            to="/signup"
                            className="px-7 py-3.5 rounded-xl bg-slate-900 text-white font-bold hover:bg-cyan-600 shadow-lg shadow-slate-900/10 hover:shadow-cyan-600/25 transition-all duration-300 flex items-center gap-2 group"
                        >
                            Get Started
                            <svg className="w-4 h-4 transition-transform group-hover:translate-x-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                            </svg>
                        </Link>
                        <Link
                            to="/login"
                            className="px-7 py-3.5 rounded-xl border border-slate-300 font-bold text-slate-700 hover:text-slate-900 hover:bg-slate-50 transition-all duration-200"
                        >
                            Sign In
                        </Link>
                    </div>

                    <div className="pt-6 border-t border-slate-100 grid grid-cols-3 gap-4">
                        <div>
                            <p className="text-2xl sm:text-3xl font-black text-slate-900">98%</p>
                            <p className="text-xs text-slate-500 font-medium">Match Accuracy</p>
                        </div>
                        <div>
                            <p className="text-2xl sm:text-3xl font-black text-slate-900">10x</p>
                            <p className="text-xs text-slate-500 font-medium">Faster Screening</p>
                        </div>
                        <div>
                            <p className="text-2xl sm:text-3xl font-black text-slate-900">100%</p>
                            <p className="text-xs text-slate-500 font-medium">Deterministic Gaps</p>
                        </div>
                    </div>
                </div>

                <div className="text-xs text-slate-400 font-medium">
                    © {new Date().getFullYear()} CareerConnect. All rights reserved.
                </div>
            </div>

            {/* PART 2: FULL SCREEN ROCKET BACKGROUND WITH 3 MOVING IMAGES (RIGHT SIDE) */}
            <div className="w-full lg:w-1/2 relative min-h-[500px] lg:min-h-full flex items-center justify-center p-6 sm:p-8 lg:p-10 xl:p-12 overflow-hidden bg-slate-950 flex-1">
                {/* Rocket background image with opacity, full screen */}
                <div
                    className="absolute inset-0 bg-cover select-none pointer-events-none transition-transform duration-700 opacity-80"
                    style={{
                        backgroundImage: "url('/images/career-launch-hero.jpg')",
                        backgroundPosition: "center",
                        transform: "scale(1.12) translate(-25px, -45px)",
                    }}
                />

                {/* Subtle cosmic gradient overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-slate-950/75 via-slate-950/15 to-slate-950/35 pointer-events-none" />

                {/* The 3 Moving Images Slider - Full Opacity with Rounded Border */}
                <div
                    className="relative z-10 w-full max-w-[480px] xl:max-w-[530px] 2xl:max-w-[560px] group"
                    onMouseEnter={() => setIsHovered(true)}
                    onMouseLeave={() => setIsHovered(false)}
                >
                    {/* Ambient glow behind cards */}
                    <div className="absolute -inset-2 bg-gradient-to-r from-cyan-500/25 via-blue-600/20 to-purple-600/25 rounded-3xl blur-xl opacity-70 group-hover:opacity-95 transition-opacity duration-500 -z-10" />

                    {/* Rounded Image Container */}
                    <div className="relative rounded-3xl overflow-hidden aspect-[16/10.5] max-h-[340px] xl:max-h-[380px] bg-white border-2 border-white/90 shadow-2xl shadow-slate-950/80">
                        <div
                            className="flex h-full w-full"
                            onTransitionEnd={handleTransitionEnd}
                            style={{
                                transform: `translateX(-${currentSlide * 100}%)`,
                                transition: isTransitioning ? 'transform 600ms cubic-bezier(0.4, 0, 0.2, 1)' : 'none',
                            }}
                        >
                            {EXTENDED_SLIDES.map((slide, idx) => (
                                <div key={`${slide.id}-${idx}`} className="min-w-full h-full relative shrink-0 overflow-hidden">
                                    <img
                                        src={slide.image}
                                        alt={slide.alt}
                                        className="w-full h-full object-cover select-none pointer-events-none opacity-100"
                                        draggable={false}
                                    />
                                    {/* Caption Overlay */}
                                    <div className="absolute inset-x-0 bottom-0 bg-slate-950/75 backdrop-blur-md border-t border-white/10 p-3.5 sm:p-4 text-white">
                                        <h3 className="text-xs sm:text-sm font-bold drop-shadow-sm text-white">{slide.title}</h3>
                                        <p className="text-[11px] sm:text-xs text-slate-200 font-medium drop-shadow-sm hidden sm:block line-clamp-1">{slide.subtitle}</p>
                                    </div>
                                </div>
                            ))}
                        </div>

                        {/* Navigation Arrows */}
                        <button
                            type="button"
                            onClick={() => {
                                setIsTransitioning(true);
                                setCurrentSlide((prev) => prev - 1);
                            }}
                            className="absolute left-2.5 top-1/2 -translate-y-1/2 z-30 w-8 h-8 rounded-full bg-slate-900/60 hover:bg-slate-900 text-white flex items-center justify-center backdrop-blur-md border border-white/30 opacity-0 group-hover:opacity-100 transition-all duration-200 shadow-xl text-lg font-bold"
                            aria-label="Previous slide"
                        >
                            ‹
                        </button>
                        <button
                            type="button"
                            onClick={() => {
                                setIsTransitioning(true);
                                setCurrentSlide((prev) => prev + 1);
                            }}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 z-30 w-8 h-8 rounded-full bg-slate-900/60 hover:bg-slate-900 text-white flex items-center justify-center backdrop-blur-md border border-white/30 opacity-0 group-hover:opacity-100 transition-all duration-200 shadow-xl text-lg font-bold"
                            aria-label="Next slide"
                        >
                            ›
                        </button>

                        {/* Pagination Indicators */}
                        <div className="absolute bottom-3 right-3 z-30 flex items-center gap-1.5 bg-black/50 backdrop-blur-md px-2.5 py-1 rounded-full border border-white/20 shadow-xl">
                            {SLIDES.map((_, idx) => (
                                <button
                                    type="button"
                                    key={idx}
                                    onClick={() => handleDotClick(idx)}
                                    className={`h-1.5 rounded-full transition-all duration-300 ${
                                        activeIndex === idx ? 'w-5 bg-cyan-400 shadow-sm' : 'w-1.5 bg-white/40 hover:bg-white/70'
                                    }`}
                                    aria-label={`Go to slide ${idx + 1}`}
                                />
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default LandingPage;
