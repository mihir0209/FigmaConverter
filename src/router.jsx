import { lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';

const Desktop1 = lazy(() => import('./components/Desktop-1'));
const Desktop2 = lazy(() => import('./components/Desktop-2'));
const Desktop3 = lazy(() => import('./components/Desktop-3'));
const Desktop4 = lazy(() => import('./components/Desktop-4'));
const Desktop5 = lazy(() => import('./components/Desktop-5'));
const Desktop6 = lazy(() => import('./components/Desktop-6'));

function LoadingFallback() {
  return (
    <div className="flex h-screen items-center justify-center bg-white">
      <div className="h-12 w-12 animate-spin rounded-full border-4 border-green border-t-transparent" />
    </div>
  );
}

export default function AppRouter() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <Routes>
        <Route path="/" element={<Desktop1 />} />
        <Route path="/dashboard" element={<Desktop2 />} />
        <Route path="/details" element={<Desktop3 />} />
        <Route path="/manage/:id" element={<Desktop4 />} />
        <Route path="/settings" element={<Desktop5 />} />
        <Route path="/confirmation" element={<Desktop6 />} />
      </Routes>
    </Suspense>
  );
}
