import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { api } from '../api';

export interface ResourceUsage {
  cpu_percent: number;
  memory_mb: number;
  disk_mb: number;
  container_count: number;
  last_updated: string;
}

export interface Session {
  session_id: string;
  user_id: string;
  name: string;
  state: string;
  created_at: string;
  last_active: string;
  resource_usage: ResourceUsage;
  metadata: Record<string, string>;
  error_message?: string;
}

interface SessionState {
  sessions: Session[];
  currentSession?: Session;
  loading: boolean;
  error?: string;
  
  // Actions
  fetchSessions: () => Promise<void>;
  createSession: (name: string, metadata?: Record<string, string>) => Promise<Session>;
  switchSession: (sessionId: string) => Promise<void>;
  stopSession: (sessionId: string) => Promise<void>;
  pauseSession: (sessionId: string) => Promise<void>;
  resumeSession: (sessionId: string) => Promise<void>;
  updateSession: (sessionId: string, name?: string, metadata?: Record<string, string>) => Promise<void>;
}

export const useSessionStore = create<SessionState>()(
  devtools(
    (set, get) => ({
      sessions: [],
      loading: false,
      
      fetchSessions: async () => {
        set({ loading: true, error: undefined });
        try {
          const response = await api.get<Session[]>('/api/sessions');
          set({ sessions: response.data });
        } catch (error) {
          set({ error: 'Failed to fetch sessions' });
        } finally {
          set({ loading: false });
        }
      },
      
      createSession: async (name: string, metadata?: Record<string, string>) => {
        set({ loading: true, error: undefined });
        try {
          const response = await api.post<Session>('/api/sessions', {
            name,
            metadata
          });
          const newSession = response.data;
          set(state => ({
            sessions: [...state.sessions, newSession],
            currentSession: newSession
          }));
          return newSession;
        } catch (error) {
          set({ error: 'Failed to create session' });
          throw error;
        } finally {
          set({ loading: false });
        }
      },
      
      switchSession: async (sessionId: string) => {
        const session = get().sessions.find(s => s.session_id === sessionId);
        if (!session) {
          throw new Error('Session not found');
        }
        set({ currentSession: session });
      },
      
      stopSession: async (sessionId: string) => {
        set({ loading: true, error: undefined });
        try {
          await api.post(`/api/sessions/${sessionId}/stop`);
          set(state => ({
            sessions: state.sessions.filter(s => s.session_id !== sessionId),
            currentSession: state.currentSession?.session_id === sessionId
              ? undefined
              : state.currentSession
          }));
        } catch (error) {
          set({ error: 'Failed to stop session' });
          throw error;
        } finally {
          set({ loading: false });
        }
      },
      
      pauseSession: async (sessionId: string) => {
        set({ loading: true, error: undefined });
        try {
          await api.post(`/api/sessions/${sessionId}/pause`);
          set(state => ({
            sessions: state.sessions.map(s =>
              s.session_id === sessionId
                ? { ...s, state: 'PAUSED' }
                : s
            ),
            currentSession: state.currentSession?.session_id === sessionId
              ? { ...state.currentSession, state: 'PAUSED' }
              : state.currentSession
          }));
        } catch (error) {
          set({ error: 'Failed to pause session' });
          throw error;
        } finally {
          set({ loading: false });
        }
      },
      
      resumeSession: async (sessionId: string) => {
        set({ loading: true, error: undefined });
        try {
          await api.post(`/api/sessions/${sessionId}/resume`);
          set(state => ({
            sessions: state.sessions.map(s =>
              s.session_id === sessionId
                ? { ...s, state: 'RUNNING' }
                : s
            ),
            currentSession: state.currentSession?.session_id === sessionId
              ? { ...state.currentSession, state: 'RUNNING' }
              : state.currentSession
          }));
        } catch (error) {
          set({ error: 'Failed to resume session' });
          throw error;
        } finally {
          set({ loading: false });
        }
      },
      
      updateSession: async (sessionId: string, name?: string, metadata?: Record<string, string>) => {
        set({ loading: true, error: undefined });
        try {
          const response = await api.patch<Session>(`/api/sessions/${sessionId}`, {
            name,
            metadata
          });
          const updatedSession = response.data;
          set(state => ({
            sessions: state.sessions.map(s =>
              s.session_id === sessionId ? updatedSession : s
            ),
            currentSession: state.currentSession?.session_id === sessionId
              ? updatedSession
              : state.currentSession
          }));
        } catch (error) {
          set({ error: 'Failed to update session' });
          throw error;
        } finally {
          set({ loading: false });
        }
      }
    })
  )
);