import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../../src/utils/api';
import { colors } from '../../src/utils/colors';
import { Card } from '../../src/components/Card';
import { LoadingSpinner } from '../../src/components/LoadingSpinner';
import { useAuthStore } from '../../src/store/authStore';
import { DashboardData, Assignment, Note } from '../../src/types';
import { format, isToday, isTomorrow, formatDistanceToNow } from 'date-fns';

export default function HomeScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const response = await api.get('/dashboard');
      setDashboard(response.data);
    } catch (error) {
      console.error('Error loading dashboard:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    loadDashboard();
  };

  const formatDueDate = (dateStr: string) => {
    const date = new Date(dateStr);
    if (isToday(date)) return 'Due Today';
    if (isTomorrow(date)) return 'Due Tomorrow';
    return `Due ${format(date, 'MMM d')}`;
  };

  if (loading) {
    return <LoadingSpinner text="Loading dashboard..." />;
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Welcome Header */}
      <LinearGradient
        colors={[colors.primary, colors.primaryDark]}
        style={styles.header}
      >
        <View style={styles.headerContent}>
          <View>
            <Text style={styles.greeting}>Welcome back,</Text>
            <Text style={styles.userName}>{user?.name?.split(' ')[0]}!</Text>
          </View>
          <TouchableOpacity
            style={styles.syncButton}
            onPress={async () => {
              try {
                await api.get('/sync/classroom');
                loadDashboard();
                alert('Synced successfully!');
              } catch (error) {
                alert('Failed to sync');
              }
            }}
          >
            <Ionicons name="sync" size={24} color="#FFF" />
          </TouchableOpacity>
        </View>
      </LinearGradient>

      <View style={styles.content}>
        {/* Quick Stats */}
        <View style={styles.statsRow}>
          <Card style={styles.statCard}>
            <Ionicons name="book" size={32} color={colors.primary} />
            <Text style={styles.statNumber}>{dashboard?.courses_count || 0}</Text>
            <Text style={styles.statLabel}>Courses</Text>
          </Card>
          <Card style={styles.statCard}>
            <Ionicons name="checkbox" size={32} color={colors.secondary} />
            <Text style={styles.statNumber}>
              {dashboard?.upcoming_assignments?.length || 0}
            </Text>
            <Text style={styles.statLabel}>Upcoming</Text>
          </Card>
          <Card style={styles.statCard}>
            <Ionicons name="document-text" size={32} color={colors.warning} />
            <Text style={styles.statNumber}>
              {dashboard?.recent_notes?.length || 0}
            </Text>
            <Text style={styles.statLabel}>Notes</Text>
          </Card>
        </View>

        {/* Today's Tasks */}
        {dashboard?.today_assignments && dashboard.today_assignments.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>📅 Due Today</Text>
            {dashboard.today_assignments.map((assignment) => (
              <AssignmentCard
                key={assignment.id}
                assignment={assignment}
                onPress={() => router.push('/assignments')}
              />
            ))}
          </View>
        )}

        {/* Upcoming Assignments */}
        {dashboard?.upcoming_assignments &&
          dashboard.upcoming_assignments.length > 0 && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Text style={styles.sectionTitle}>📚 Upcoming Assignments</Text>
                <TouchableOpacity onPress={() => router.push('/assignments')}>
                  <Text style={styles.seeAll}>See All</Text>
                </TouchableOpacity>
              </View>
              {dashboard.upcoming_assignments.slice(0, 3).map((assignment) => (
                <AssignmentCard
                  key={assignment.id}
                  assignment={assignment}
                  onPress={() => router.push('/assignments')}
                />
              ))}
            </View>
          )}

        {/* Recent Notes */}
        {dashboard?.recent_notes && dashboard.recent_notes.length > 0 && (
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>📝 Recent Notes</Text>
              <TouchableOpacity onPress={() => router.push('/courses')}>
                <Text style={styles.seeAll}>See All</Text>
              </TouchableOpacity>
            </View>
            {dashboard.recent_notes.slice(0, 3).map((note) => (
              <NoteCard
                key={note.id}
                note={note}
                onPress={() => router.push('/courses')}
              />
            ))}
          </View>
        )}

        {/* Quick Actions */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>⚡ Quick Actions</Text>
          <View style={styles.actionsRow}>
            <TouchableOpacity
              style={[styles.actionButton, { backgroundColor: colors.primary }]}
              onPress={() => router.push('/tutor')}
            >
              <Ionicons name="chatbubbles" size={24} color="#FFF" />
              <Text style={styles.actionText}>Ask AI</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.actionButton, { backgroundColor: colors.secondary }]}
              onPress={() => router.push('/courses')}
            >
              <Ionicons name="add-circle" size={24} color="#FFF" />
              <Text style={styles.actionText}>New Note</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </ScrollView>
  );
}

const AssignmentCard = ({
  assignment,
  onPress,
}: {
  assignment: Assignment;
  onPress: () => void;
}) => (
  <Card style={styles.assignmentCard} onPress={onPress}>
    <View style={styles.assignmentContent}>
      <View style={styles.assignmentInfo}>
        <Text style={styles.assignmentTitle} numberOfLines={2}>
          {assignment.title}
        </Text>
        <Text style={styles.assignmentDue}>
          {assignment.due_date && formatDueDate(assignment.due_date)}
        </Text>
      </View>
      <Ionicons name="chevron-forward" size={24} color={colors.textMuted} />
    </View>
  </Card>
);

const NoteCard = ({ note, onPress }: { note: Note; onPress: () => void }) => (
  <Card style={styles.noteCard} onPress={onPress}>
    <View style={styles.noteContent}>
      <Ionicons name="document-text" size={20} color={colors.primary} />
      <View style={styles.noteInfo}>
        <Text style={styles.noteTitle} numberOfLines={1}>
          {note.title}
        </Text>
        <Text style={styles.noteTime}>
          {formatDistanceToNow(new Date(note.updated_at), { addSuffix: true })}
        </Text>
      </View>
    </View>
  </Card>
);

const formatDueDate = (dateStr: string) => {
  const date = new Date(dateStr);
  if (isToday(date)) return '🔴 Due Today';
  if (isTomorrow(date)) return '🟡 Due Tomorrow';
  return `🟢 Due ${format(date, 'MMM d')}`;
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    paddingTop: 60,
    paddingHorizontal: 24,
    paddingBottom: 32,
    borderBottomLeftRadius: 24,
    borderBottomRightRadius: 24,
  },
  headerContent: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  greeting: {
    fontSize: 16,
    color: 'rgba(255, 255, 255, 0.9)',
  },
  userName: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#FFF',
    marginTop: 4,
  },
  syncButton: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  content: {
    padding: 24,
  },
  statsRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 24,
  },
  statCard: {
    flex: 1,
    alignItems: 'center',
    padding: 16,
  },
  statNumber: {
    fontSize: 24,
    fontWeight: 'bold',
    color: colors.text,
    marginTop: 8,
  },
  statLabel: {
    fontSize: 12,
    color: colors.textLight,
    marginTop: 4,
  },
  section: {
    marginBottom: 24,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: colors.text,
    marginBottom: 12,
  },
  seeAll: {
    fontSize: 14,
    color: colors.primary,
    fontWeight: '600',
  },
  assignmentCard: {
    marginBottom: 12,
  },
  assignmentContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  assignmentInfo: {
    flex: 1,
  },
  assignmentTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 4,
  },
  assignmentDue: {
    fontSize: 14,
    color: colors.textLight,
  },
  noteCard: {
    marginBottom: 12,
  },
  noteContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  noteInfo: {
    flex: 1,
  },
  noteTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 4,
  },
  noteTime: {
    fontSize: 12,
    color: colors.textLight,
  },
  actionsRow: {
    flexDirection: 'row',
    gap: 12,
  },
  actionButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
    borderRadius: 12,
    gap: 8,
  },
  actionText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
});