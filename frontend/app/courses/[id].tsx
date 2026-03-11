import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Linking,
  Alert,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { colors } from '../../src/utils/colors';
import { Card } from '../../src/components/Card';
import { LoadingSpinner } from '../../src/components/LoadingSpinner';
import { format } from 'date-fns';

export default function CourseDetailScreen() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const [course, setCourse] = useState<any>(null);
  const [files, setFiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadCourseDetails();
  }, [id]);

  const loadCourseDetails = async () => {
    try {
      // Load course info
      const courseRes = await api.get(`/courses/${id}`);
      setCourse(courseRes.data);

      // Load files
      const filesRes = await api.get(`/courses/${id}/files`);
      setFiles(filesRes.data.files);
    } catch (error) {
      console.error('Error loading course details:', error);
      Alert.alert('Error', 'Failed to load course details');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    loadCourseDetails();
  };

  const downloadCourseFiles = async () => {
    try {
      const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;
      const downloadUrl = `${BACKEND_URL}/api/courses/${id}/download`;
      
      Alert.alert(
        'Download Files',
        'Opening browser to download all course files...',
        [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'Download',
            onPress: () => Linking.openURL(downloadUrl),
          },
        ]
      );
    } catch (error) {
      Alert.alert('Error', 'Failed to download files');
    }
  };

  const viewFile = (file: any) => {
    Alert.alert(
      file.title,
      file.content_preview,
      [
        { text: 'Close', style: 'cancel' },
        {
          text: 'Ask AI',
          onPress: () => router.push(`/(tabs)/tutor?file=${file.id}`),
        },
      ]
    );
  };

  if (loading) {
    return <LoadingSpinner text="Loading course..." />;
  }

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <View style={styles.headerContent}>
          <Text style={styles.courseName}>{course?.name}</Text>
          <Text style={styles.courseSection}>{course?.section || ''}</Text>
        </View>
      </View>

      <ScrollView
        style={styles.scrollView}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        <View style={styles.content}>
          {/* Stats */}
          <View style={styles.statsRow}>
            <Card style={styles.statCard}>
              <Ionicons name="document-text" size={24} color={colors.primary} />
              <Text style={styles.statNumber}>{files.length}</Text>
              <Text style={styles.statLabel}>Files</Text>
            </Card>
            <Card style={styles.statCard}>
              <Ionicons name="calendar" size={24} color={colors.secondary} />
              <Text style={styles.statNumber}>0</Text>
              <Text style={styles.statLabel}>Assignments</Text>
            </Card>
          </View>

          {/* Actions */}
          <View style={styles.actionsRow}>
            <TouchableOpacity
              style={[styles.actionButton, { backgroundColor: colors.primary }]}
              onPress={downloadCourseFiles}
            >
              <Ionicons name="download" size={20} color="#FFF" />
              <Text style={styles.actionText}>Download All</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.actionButton, { backgroundColor: colors.secondary }]}
              onPress={() => router.push(`/(tabs)/tutor?course=${id}`)}
            >
              <Ionicons name="chatbubbles" size={20} color="#FFF" />
              <Text style={styles.actionText}>Ask AI</Text>
            </TouchableOpacity>
          </View>

          {/* Files List */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>📄 Course Materials</Text>
            
            {files.length === 0 ? (
              <Card style={styles.emptyCard}>
                <Ionicons name="folder-open-outline" size={48} color={colors.textMuted} />
                <Text style={styles.emptyText}>No files synced yet</Text>
                <Text style={styles.emptySubtext}>Sync from Google Classroom to see materials</Text>
              </Card>
            ) : (
              files.map((file) => (
                <Card key={file.id} style={styles.fileCard} onPress={() => viewFile(file)}>
                  <View style={styles.fileContent}>
                    <View style={styles.fileIcon}>
                      <Ionicons
                        name={file.file_type === 'PDF' ? 'document-text' : 'document'}
                        size={24}
                        color={colors.primary}
                      />
                    </View>
                    <View style={styles.fileInfo}>
                      <Text style={styles.fileName} numberOfLines={2}>
                        {file.title}
                      </Text>
                      <View style={styles.fileMeta}>
                        <Text style={styles.fileType}>{file.file_type}</Text>
                        <Text style={styles.fileSize}>
                          {Math.round(file.content_length / 1024)} KB
                        </Text>
                        <Text style={styles.fileDate}>
                          {format(new Date(file.created_at), 'MMM d')}
                        </Text>
                      </View>
                    </View>
                    <Ionicons name="chevron-forward" size={24} color={colors.textMuted} />
                  </View>
                </Card>
              ))
            )}
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    backgroundColor: colors.primary,
    paddingTop: 50,
    paddingBottom: 20,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerContent: {
    flex: 1,
  },
  courseName: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#FFF',
  },
  courseSection: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.9)',
    marginTop: 4,
  },
  scrollView: {
    flex: 1,
  },
  content: {
    padding: 16,
  },
  statsRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
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
  actionsRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 24,
  },
  actionButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 14,
    borderRadius: 12,
    gap: 8,
  },
  actionText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFF',
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
  emptyCard: {
    padding: 40,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginTop: 12,
  },
  emptySubtext: {
    fontSize: 14,
    color: colors.textLight,
    marginTop: 4,
    textAlign: 'center',
  },
  fileCard: {
    marginBottom: 12,
  },
  fileContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  fileIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: `${colors.primary}20`,
    alignItems: 'center',
    justifyContent: 'center',
  },
  fileInfo: {
    flex: 1,
  },
  fileName: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 4,
  },
  fileMeta: {
    flexDirection: 'row',
    gap: 12,
  },
  fileType: {
    fontSize: 12,
    color: colors.primary,
    fontWeight: '600',
  },
  fileSize: {
    fontSize: 12,
    color: colors.textLight,
  },
  fileDate: {
    fontSize: 12,
    color: colors.textLight,
  },
});
