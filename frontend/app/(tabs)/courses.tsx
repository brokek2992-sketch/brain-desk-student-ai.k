import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { colors } from '../../src/utils/colors';
import { Card } from '../../src/components/Card';
import { LoadingSpinner } from '../../src/components/LoadingSpinner';
import { Course } from '../../src/types';

export default function CoursesScreen() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadCourses();
  }, []);

  const loadCourses = async () => {
    try {
      const response = await api.get('/courses');
      setCourses(response.data);
    } catch (error) {
      console.error('Error loading courses:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    loadCourses();
  };

  const syncClassroom = async () => {
    try {
      setLoading(true);
      await api.get('/sync/classroom');
      await loadCourses();
      alert('Synced successfully!');
    } catch (error) {
      alert('Failed to sync');
    } finally {
      setLoading(false);
    }
  };

  if (loading && courses.length === 0) {
    return <LoadingSpinner text="Loading courses..." />;
  }

  return (
    <View style={styles.container}>
      <ScrollView
        style={styles.scrollView}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        <View style={styles.content}>
          {/* Sync Button */}
          <TouchableOpacity
            style={styles.syncButton}
            onPress={syncClassroom}
            disabled={loading}
          >
            <Ionicons name="sync" size={20} color="#FFF" />
            <Text style={styles.syncButtonText}>Sync Google Classroom</Text>
          </TouchableOpacity>

          {courses.length === 0 ? (
            <View style={styles.emptyState}>
              <Ionicons name="book-outline" size={64} color={colors.textMuted} />
              <Text style={styles.emptyTitle}>No Courses Yet</Text>
              <Text style={styles.emptyText}>
                Sync with Google Classroom to see your courses
              </Text>
            </View>
          ) : (
            <View style={styles.coursesGrid}>
              {courses.map((course) => (
                <CourseCard key={course.id} course={course} />
              ))}
            </View>
          )}
        </View>
      </ScrollView>
    </View>
  );
}

const CourseCard = ({ course }: { course: Course }) => {
  const courseColors = [
    [colors.primary, colors.primaryDark],
    [colors.secondary, colors.secondaryDark],
    ['#FF6B6B', '#EE5A6F'],
    ['#4ECDC4', '#44A08D'],
    ['#A8E6CF', '#3D9970'],
    ['#FFD93D', '#F39C12'],
  ];

  const colorIndex = Math.abs(
    course.name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
  ) % courseColors.length;

  return (
    <Card style={styles.courseCard}>
      <View
        style={[
          styles.courseHeader,
          { backgroundColor: courseColors[colorIndex][0] },
        ]}
      >
        <Ionicons name="book" size={32} color="#FFF" />
      </View>
      <View style={styles.courseBody}>
        <Text style={styles.courseName} numberOfLines={2}>
          {course.name}
        </Text>
        {course.section && (
          <Text style={styles.courseSection}>{course.section}</Text>
        )}
        <View style={styles.courseStats}>
          <View style={styles.statItem}>
            <Ionicons name="document-text" size={16} color={colors.primary} />
            <Text style={styles.statText}>{course.notes_count || 0} notes</Text>
          </View>
          <View style={styles.statItem}>
            <Ionicons name="checkbox" size={16} color={colors.secondary} />
            <Text style={styles.statText}>
              {course.assignments_count || 0} tasks
            </Text>
          </View>
        </View>
      </View>
    </Card>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollView: {
    flex: 1,
  },
  content: {
    padding: 16,
  },
  syncButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    padding: 16,
    borderRadius: 12,
    marginBottom: 16,
    gap: 8,
  },
  syncButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 80,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: colors.text,
    marginTop: 16,
  },
  emptyText: {
    fontSize: 16,
    color: colors.textLight,
    textAlign: 'center',
    marginTop: 8,
    paddingHorizontal: 32,
  },
  coursesGrid: {
    gap: 16,
  },
  courseCard: {
    padding: 0,
    overflow: 'hidden',
  },
  courseHeader: {
    padding: 20,
    alignItems: 'center',
  },
  courseBody: {
    padding: 16,
  },
  courseName: {
    fontSize: 18,
    fontWeight: 'bold',
    color: colors.text,
    marginBottom: 4,
  },
  courseSection: {
    fontSize: 14,
    color: colors.textLight,
    marginBottom: 12,
  },
  courseStats: {
    flexDirection: 'row',
    gap: 16,
  },
  statItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  statText: {
    fontSize: 14,
    color: colors.textLight,
  },
});