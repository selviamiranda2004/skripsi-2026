'use client';

import { useAuth } from '@/context/AuthContext';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { SWRConfig } from 'swr';

const publicRoutes = ['/login'];

// Global SWR config — bikin frontend jauh lebih ringan:
//  - revalidateOnFocus: false  -> tidak refetch tiap pindah tab/window
//  - revalidateOnReconnect: false -> tidak refetch tiap network blip
//  - dedupingInterval: 60_000  -> request URL sama dalam 60s di-cache
//  - keepPreviousData: true    -> UI tidak flash blank saat refresh
//  - errorRetryCount: 2        -> stop nge-spam request kalau backend error
const swrConfig = {
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
  dedupingInterval: 60_000,
  keepPreviousData: true,
  errorRetryCount: 2,
  errorRetryInterval: 5000,
};

export default function RootLayoutClient({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;

    const isPublicRoute = publicRoutes.includes(pathname);

    if (!isAuthenticated && !isPublicRoute) {
      router.replace('/login');
    }

    if (isAuthenticated && pathname === '/login') {
      router.replace('/');
    }
  }, [isAuthenticated, loading, pathname, router]);

  if (loading) {
    return (
         <div className="flex items-center justify-center min-h-screen bg-white">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  const isPublicRoute = publicRoutes.includes(pathname);
  if (!isAuthenticated && !isPublicRoute) {
    return null;
  }

  return <SWRConfig value={swrConfig}>{children}</SWRConfig>;
}