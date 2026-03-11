import React, { useEffect } from 'react';
import { Redirect, useLocalSearchParams } from 'expo-router';
import { useAuthStore } from '../src/store/authStore';
import { LoadingSpinner } from '../src/components/LoadingSpinner';
import api from '../src/utils/api';

export default function Index() {
  const { isAuthenticated, isLoading, checkAuth, setUser } = useAuthStore();
  const params = useLocalSearchParams();

  useEffect(() => {
    handleAuth();
  }, []);

  const handleAuth = async () => {
    // Check if returning from OAuth with user_id
    if (params.auth_success && params.user_id) {
      try {
        // Fetch user data from backend using user_id
        const response = await api.get(`/auth/user/${params.user_id}`);
        setUser(response.data);
      } catch (error) {
        console.error('Error fetching user after OAuth:', error);
        checkAuth(); // Fall back to normal auth check
      }
    } else {
      checkAuth();
    }
  };

  if (isLoading) {
    return <LoadingSpinner text="Loading..." />;
  }

  if (!isAuthenticated) {
    return <Redirect href="/auth/login" />;
  }

  return <Redirect href="/(tabs)/home" />;
}