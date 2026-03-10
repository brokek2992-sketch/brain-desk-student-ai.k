import React, { useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Image } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import * as WebBrowser from 'expo-web-browser';
import { useAuthStore } from '../../src/store/authStore';
import { colors } from '../../src/utils/colors';
import { LoadingSpinner } from '../../src/components/LoadingSpinner';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';

WebBrowser.maybeCompleteAuthSession();

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

export default function AuthScreen() {
  const { checkAuth, isLoading, setUser } = useAuthStore();

  useEffect(() => {
    checkAuth();
  }, []);

  const handleGoogleLogin = async () => {
    try {
      // Get authorization URL from backend
      const response = await api.get('/auth/login');
      const { authorization_url } = response.data;

      // Open browser for OAuth
      const result = await WebBrowser.openAuthSessionAsync(
        authorization_url,
        `${BACKEND_URL}/api/auth/callback`
      );

      if (result.type === 'success') {
        // Check if user is authenticated
        const userResponse = await api.get('/auth/me');
        setUser(userResponse.data);
      }
    } catch (error) {
      console.error('Login error:', error);
      alert('Failed to login. Please try again.');
    }
  };

  if (isLoading) {
    return <LoadingSpinner text="Loading..." />;
  }

  return (
    <LinearGradient
      colors={[colors.primary, colors.primaryDark, colors.indigo]}
      style={styles.container}
    >
      <View style={styles.content}>
        <View style={styles.logoContainer}>
          <View style={styles.logoCircle}>
            <Ionicons name="school" size={64} color="#FFF" />
          </View>
          <Text style={styles.title}>Brain Desk</Text>
          <Text style={styles.subtitle}>
            Your AI-powered study companion
          </Text>
        </View>

        <View style={styles.featuresContainer}>
          <FeatureItem
            icon="book"
            text="Organize notes and assignments"
          />
          <FeatureItem
            icon="chatbubbles"
            text="Chat with AI tutor"
          />
          <FeatureItem
            icon="calendar"
            text="Sync with Google Classroom"
          />
          <FeatureItem
            icon="create"
            text="Generate quizzes and tests"
          />
        </View>

        <TouchableOpacity
          style={styles.loginButton}
          onPress={handleGoogleLogin}
          activeOpacity={0.8}
        >
          <Ionicons name="logo-google" size={24} color={colors.primary} />
          <Text style={styles.loginButtonText}>Continue with Google</Text>
        </TouchableOpacity>

        <Text style={styles.disclaimer}>
          Connect your Google Classroom to get started
        </Text>
      </View>
    </LinearGradient>
  );
}

const FeatureItem = ({ icon, text }: { icon: any; text: string }) => (
  <View style={styles.featureItem}>
    <Ionicons name={icon} size={24} color="#FFF" />
    <Text style={styles.featureText}>{text}</Text>
  </View>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    flex: 1,
    padding: 24,
    justifyContent: 'space-between',
  },
  logoContainer: {
    alignItems: 'center',
    marginTop: 60,
  },
  logoCircle: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  title: {
    fontSize: 42,
    fontWeight: 'bold',
    color: '#FFF',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 18,
    color: 'rgba(255, 255, 255, 0.9)',
    textAlign: 'center',
  },
  featuresContainer: {
    gap: 16,
  },
  featureItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.15)',
    padding: 16,
    borderRadius: 12,
    gap: 16,
  },
  featureText: {
    fontSize: 16,
    color: '#FFF',
    flex: 1,
  },
  loginButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFF',
    padding: 18,
    borderRadius: 12,
    gap: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  loginButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.primary,
  },
  disclaimer: {
    fontSize: 14,
    color: 'rgba(255, 255, 255, 0.8)',
    textAlign: 'center',
  },
});