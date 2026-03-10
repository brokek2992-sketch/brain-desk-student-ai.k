import React, { useEffect } from 'react';
import { Redirect } from 'expo-router';
import { useAuthStore } from './src/store/authStore';
import { LoadingSpinner } from './src/components/LoadingSpinner';

export default function Index() {
  const { isAuthenticated, isLoading, checkAuth } = useAuthStore();

  useEffect(() => {
    checkAuth();
  }, []);

  if (isLoading) {
    return <LoadingSpinner text="Loading..." />;
  }

  if (!isAuthenticated) {
    return <Redirect href="/auth/login" />;
  }

  return <Redirect href="/home" />;
}