import React, { useEffect, useState } from 'react';
import { Redirect, useLocalSearchParams } from 'expo-router';
import { useAuthStore } from '../src/store/authStore';
import { LoadingSpinner } from '../src/components/LoadingSpinner';
import api from '../src/utils/api';

export default function Index() {
  const { isAuthenticated, setUser } = useAuthStore();
  const params = useLocalSearchParams();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    handleAuth();
  }, []);

  const handleAuth = async () => {
    try {
      // Check if returning from OAuth with user_id
      if (params.auth_success && params.user_id) {
        console.log('OAuth callback detected, fetching user:', params.user_id);
        // Fetch user data from backend using user_id
        const response = await api.get(`/auth/user/${params.user_id}`);
        console.log('User fetched successfully:', response.data.email);
        setUser(response.data);
      } else {
        // Check AsyncStorage for existing user
        const { checkAuth } = useAuthStore.getState();
        await checkAuth();
      }
    } catch (error) {
      console.error('Error fetching user after OAuth:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <LoadingSpinner text="Loading..." />;
  }

  if (!isAuthenticated) {
    return <Redirect href="/auth/login" />;
  }

  // Redirect to home (inside tabs)
  return <Redirect href="/(tabs)/home" />;
}