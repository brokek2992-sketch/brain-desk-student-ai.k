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
import { Assignment } from '../../src/types';
import { format, isToday, isTomorrow, isPast } from 'date-fns';

export default function AssignmentsScreen() {
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<'all' | 'pending' | 'completed'>('all');

  useEffect(() => {
    loadAssignments();
  }, []);

  const loadAssignments = async () => {
    try {
      const response = await api.get('/assignments');
      setAssignments(response.data);
    } catch (error) {
      console.error('Error loading assignments:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    loadAssignments();
  };

  const completeAssignment = async (id: string) => {
    try {
      await api.patch(`/assignments/${id}/complete`);
      loadAssignments();
    } catch (error) {
      alert('Failed to update assignment');
    }
  };

  const filteredAssignments = assignments.filter((a) => {
    if (filter === 'pending') return a.state === 'PENDING';
    if (filter === 'completed') return a.state === 'COMPLETED';
    return true;
  });

  const getDueDateColor = (dateStr?: string) => {
    if (!dateStr) return colors.textMuted;
    const date = new Date(dateStr);
    if (isPast(date) && !isToday(date)) return colors.error;
    if (isToday(date)) return colors.warning;
    return colors.success;
  };

  const formatDueDate = (dateStr?: string) => {
    if (!dateStr) return 'No due date';
    const date = new Date(dateStr);
    if (isToday(date)) return 'Due Today';
    if (isTomorrow(date)) return 'Due Tomorrow';
    if (isPast(date)) return `Overdue - ${format(date, 'MMM d')}`;
    return `Due ${format(date, 'MMM d, yyyy')}`;
  };

  if (loading) {
    return <LoadingSpinner text="Loading assignments..." />;
  }

  return (
    <View style={styles.container}>
      {/* Filter Tabs */}
      <View style={styles.filterContainer}>
        <TouchableOpacity
          style={[
            styles.filterTab,
            filter === 'all' && styles.filterTabActive,
          ]}
          onPress={() => setFilter('all')}
        >
          <Text
            style={[
              styles.filterText,
              filter === 'all' && styles.filterTextActive,
            ]}
          >
            All ({assignments.length})
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[
            styles.filterTab,
            filter === 'pending' && styles.filterTabActive,
          ]}
          onPress={() => setFilter('pending')}
        >
          <Text
            style={[
              styles.filterText,
              filter === 'pending' && styles.filterTextActive,
            ]}
          >
            Pending ({assignments.filter((a) => a.state === 'PENDING').length})
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[
            styles.filterTab,
            filter === 'completed' && styles.filterTabActive,
          ]}
          onPress={() => setFilter('completed')}
        >
          <Text
            style={[
              styles.filterText,
              filter === 'completed' && styles.filterTextActive,
            ]}
          >
            Done ({assignments.filter((a) => a.state === 'COMPLETED').length})
          </Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scrollView}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        <View style={styles.content}>
          {filteredAssignments.length === 0 ? (
            <View style={styles.emptyState}>
              <Ionicons
                name="checkbox-outline"
                size={64}
                color={colors.textMuted}
              />
              <Text style={styles.emptyTitle}>No Assignments</Text>
              <Text style={styles.emptyText}>
                {filter === 'pending'
                  ? 'All caught up!'
                  : filter === 'completed'
                  ? "You haven't completed any assignments yet"
                  : 'Sync with Google Classroom to see your assignments'}
              </Text>
            </View>
          ) : (
            filteredAssignments.map((assignment) => (
              <Card key={assignment.id} style={styles.assignmentCard}>
                <View style={styles.assignmentHeader}>
                  <TouchableOpacity
                    onPress={() => completeAssignment(assignment.id)}
                    disabled={assignment.state === 'COMPLETED'}
                  >
                    <Ionicons
                      name={
                        assignment.state === 'COMPLETED'
                          ? 'checkbox'
                          : 'checkbox-outline'
                      }
                      size={28}
                      color={
                        assignment.state === 'COMPLETED'
                          ? colors.success
                          : colors.textMuted
                      }
                    />
                  </TouchableOpacity>
                  <View style={styles.assignmentInfo}>
                    <Text
                      style={[
                        styles.assignmentTitle,
                        assignment.state === 'COMPLETED' &&
                          styles.assignmentTitleCompleted,
                      ]}
                      numberOfLines={2}
                    >
                      {assignment.title}
                    </Text>
                    {assignment.description && (
                      <Text style={styles.assignmentDescription} numberOfLines={2}>
                        {assignment.description}
                      </Text>
                    )}
                    <View style={styles.assignmentMeta}>
                      <View
                        style={[
                          styles.dueDateBadge,
                          {
                            backgroundColor: `${getDueDateColor(
                              assignment.due_date
                            )}20`,
                          },
                        ]}
                      >
                        <Ionicons
                          name="calendar"
                          size={14}
                          color={getDueDateColor(assignment.due_date)}
                        />
                        <Text
                          style={[
                            styles.dueDate,
                            { color: getDueDateColor(assignment.due_date) },
                          ]}
                        >
                          {formatDueDate(assignment.due_date)}
                        </Text>
                      </View>
                    </View>
                  </View>
                </View>
                {assignment.link && (
                  <TouchableOpacity style={styles.linkButton}>
                    <Ionicons name="link" size={16} color={colors.primary} />
                    <Text style={styles.linkText}>View in Classroom</Text>
                  </TouchableOpacity>
                )}
              </Card>
            ))
          )}
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
  filterContainer: {
    flexDirection: 'row',
    padding: 16,
    gap: 8,
    backgroundColor: '#FFF',
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  filterTab: {
    flex: 1,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    alignItems: 'center',
    backgroundColor: colors.background,
  },
  filterTabActive: {
    backgroundColor: colors.primary,
  },
  filterText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textLight,
  },
  filterTextActive: {
    color: '#FFF',
  },
  scrollView: {
    flex: 1,
  },
  content: {
    padding: 16,
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
  assignmentCard: {
    marginBottom: 12,
  },
  assignmentHeader: {
    flexDirection: 'row',
    gap: 12,
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
  assignmentTitleCompleted: {
    textDecorationLine: 'line-through',
    color: colors.textMuted,
  },
  assignmentDescription: {
    fontSize: 14,
    color: colors.textLight,
    marginBottom: 8,
  },
  assignmentMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  dueDateBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 6,
  },
  dueDate: {
    fontSize: 12,
    fontWeight: '600',
  },
  linkButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  linkText: {
    fontSize: 14,
    color: colors.primary,
    fontWeight: '600',
  },
});