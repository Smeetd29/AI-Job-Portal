import { lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import Navbar from './components/Navbar';
import ProtectedRoute from './components/ProtectedRoute';

const AuthPage = lazy(() => import('./pages/auth/AuthPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const CandidateDashboard = lazy(() => import('./pages/candidate/CandidateDashboard'));
const JobDetailsPage = lazy(() => import('./pages/candidate/JobDetailsPage'));
const AppliedJobsPage = lazy(() => import('./pages/candidate/AppliedJobsPage'));
const RecommendationsPage = lazy(() => import('./pages/candidate/RecommendationsPage'));
const AutoApplyPage = lazy(() => import('./pages/candidate/AutoApplyPage'));
const RecruiterDashboard = lazy(() => import('./pages/recruiter/RecruiterDashboard'));
const CreateJobPage = lazy(() => import('./pages/recruiter/CreateJobPage'));
const ApplicantsPage = lazy(() => import('./pages/recruiter/ApplicantsPage'));
const LandingPage = lazy(() => import('./pages/LandingPage'));

import { useLocation } from 'react-router-dom';

function AppContent() {
  const location = useLocation();
  const isLanding = location.pathname === '/';

  return (
    <div className={`min-h-screen ${isLanding ? 'bg-white h-screen overflow-hidden flex flex-col' : 'bg-gray-50'}`}>
      {!isLanding && <Navbar />}
      <main className={isLanding ? 'h-full flex-1 flex flex-col overflow-hidden' : 'pt-20 pb-12 lg:pt-24'}>
        <Suspense fallback={<div className="flex min-h-[50vh] items-center justify-center text-sm text-gray-500">Loading page...</div>}>
          <Routes>
            <Route path="/login" element={<AuthPage mode="login" />} />
            <Route path="/signup" element={<AuthPage mode="signup" />} />
            <Route path="/" element={<LandingPage />} />

            <Route element={<ProtectedRoute />}>
              <Route path="/profile" element={<ProfilePage />} />
            </Route>

            <Route element={<ProtectedRoute allowedRoles={['candidate']} />}>
              <Route path="/candidate" element={<CandidateDashboard />} />
              <Route path="/jobs/:id" element={<JobDetailsPage />} />
              <Route path="/applied-jobs" element={<AppliedJobsPage />} />
              <Route path="/recommendations" element={<RecommendationsPage />} />
              <Route path="/auto-apply" element={<AutoApplyPage />} />
            </Route>

            <Route element={<ProtectedRoute allowedRoles={['recruiter']} />}>
              <Route path="/recruiter" element={<RecruiterDashboard />} />
              <Route path="/recruiter/create-job" element={<CreateJobPage />} />
              <Route path="/recruiter/jobs/:id/applicants" element={<ApplicantsPage />} />
            </Route>
          </Routes>
        </Suspense>
      </main>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
