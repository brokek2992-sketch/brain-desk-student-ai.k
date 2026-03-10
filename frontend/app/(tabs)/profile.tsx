import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Image,
  Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useAuthStore } from '../../src/store/authStore';
import { colors } from '../../src/utils/colors';
import { Card } from '../../src/components/Card';
import api from '../../src/utils/api';

export default function ProfileScreen() {
  const router = useRouter();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    Alert.alert('Logout', 'Are you sure you want to logout?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Logout',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.post('/auth/logout');
            await logout();
            router.replace('/auth/login');
          } catch (error) {
            console.error('Logout error:', error);
          }
        },
      },
    ]);
  };

  return (
    <ScrollView style={styles.container}>
      {/* Profile Header */}
      <LinearGradient
        colors={[colors.primary, colors.primaryDark]}
        style={styles.header}
      >
        <View style={styles.profileInfo}>
          {user?.picture ? (
            <Image source={{ uri: user.picture }} style={styles.avatar} />
          ) : (
            <View style={styles.avatarPlaceholder}>
              <Ionicons name="person" size={48} color="#FFF" />
            </View>
          )}
          <Text style={styles.userName}>{user?.name}</Text>
          <Text style={styles.userEmail}>{user?.email}</Text>
        </View>
      </LinearGradient>

      <View style={styles.content}>
        {/* Connected Accounts */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Connected Accounts</Text>
          <Card style={styles.accountCard}>
            <View style={styles.accountRow}>
              <View style={styles.accountInfo}>
                <Ionicons name="logo-google" size={24} color="#4285F4" />
                <View style={styles.accountText}>
                  <Text style={styles.accountName}>Google</Text>
                  <Text style={styles.accountStatus}>Connected</Text>
                </View>
              </View>
              <View style={styles.connectedBadge}>
                <Ionicons name="checkmark-circle" size={20} color={colors.success} />
              </View>
            </View>
          </Card>
        </View>

        {/* Settings */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Settings</Text>
          
          <SettingsItem
            icon="sync"
            label="Sync with Classroom"
            onPress={async () => {
              try {
                await api.get('/sync/classroom');
                Alert.alert('Success', 'Synced with Google Classroom!');
              } catch (error) {
                Alert.alert('Error', 'Failed to sync');
              }
            }}
          />
          
          <SettingsItem
            icon="notifications"
            label="Notifications"
            onPress={() => Alert.alert('Coming Soon', 'Notification settings will be available soon')}
          />
          
          <SettingsItem
            icon="time"
            label="Study Reminders"
            onPress={() => Alert.alert('Coming Soon', 'Study reminders will be available soon')}
          />
          
          <SettingsItem
            icon="color-palette"
            label="Theme"
            onPress={() => Alert.alert('Coming Soon', 'Theme customization will be available soon')}
          />
        </View>

        {/* About */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>About</Text>
          
          <SettingsItem
            icon="help-circle"
            label="Help & Support"
            onPress={() => Alert.alert('Help', 'Contact us at support@braindesk.app')}
          />
          
          <SettingsItem
            icon="information-circle"
            label="About Brain Desk"
            onPress={() => Alert.alert('Brain Desk', 'Version 1.0.0\nYour AI-powered study companion')}
          />
          
          <SettingsItem
            icon="document-text"
            label="Privacy Policy"
            onPress={() => Alert.alert('Privacy', 'Privacy policy coming soon')}
          />
        </View>

        {/* Logout Button */}
        <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
          <Ionicons name="log-out" size={20} color={colors.error} />
          <Text style={styles.logoutText}>Logout</Text>
        </TouchableOpacity>

        <Text style={styles.version}>Brain Desk v1.0.0</Text>
      </View>
    </ScrollView>
  );
}

const SettingsItem = ({
  icon,
  label,
  onPress,
}: {
  icon: any;
  label: string;
  onPress: () => void;
}) => (
  <TouchableOpacity style={styles.settingsItem} onPress={onPress}>
    <View style={styles.settingsLeft}>
      <Ionicons name={icon} size={24} color={colors.text} />
      <Text style={styles.settingsLabel}>{label}</Text>
    </View>
    <Ionicons name="chevron-forward" size={24} color={colors.textMuted} />
  </TouchableOpacity>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    paddingTop: 60,
    paddingBottom: 40,
    alignItems: 'center',
  },
  profileInfo: {
    alignItems: 'center',
  },
  avatar: {
    width: 100,
    height: 100,
    borderRadius: 50,
    marginBottom: 16,
    borderWidth: 4,
    borderColor: '#FFF',
  },
  avatarPlaceholder: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: 'rgba(255, 255, 255, 0.3)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
    borderWidth: 4,
    borderColor: '#FFF',
  },
  userName: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#FFF',
    marginBottom: 4,
  },
  userEmail: {
    fontSize: 16,
    color: 'rgba(255, 255, 255, 0.9)',
  },
  content: {
    padding: 16,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: colors.text,
    marginBottom: 12,
  },
  accountCard: {
    padding: 16,
  },
  accountRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  accountInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  accountText: {
    gap: 4,
  },
  accountName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  accountStatus: {
    fontSize: 14,
    color: colors.success,
  },
  connectedBadge: {},
  settingsItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#FFF',
    padding: 16,
    borderRadius: 12,
    marginBottom: 8,
  },
  settingsLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  settingsLabel: {
    fontSize: 16,
    color: colors.text,
  },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFF',
    padding: 16,
    borderRadius: 12,
    marginTop: 16,
    gap: 8,
    borderWidth: 1,
    borderColor: colors.error,
  },
  logoutText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.error,
  },
  version: {
    textAlign: 'center',
    fontSize: 14,
    color: colors.textMuted,
    marginTop: 24,
    marginBottom: 32,
  },
});