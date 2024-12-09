import React, { useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  LinearProgress,
  List,
  ListItem,
  ListItemSecondaryAction,
  ListItemText,
  TextField,
  Typography,
} from '@mui/material';
import {
  Add as AddIcon,
  Pause as PauseIcon,
  PlayArrow as PlayArrowIcon,
  Stop as StopIcon,
} from '@mui/icons-material';
import { useSessionStore } from '../../stores/sessionStore';
import { SessionResourceMonitor } from './SessionResourceMonitor';

export const SessionManager: React.FC = () => {
  const {
    sessions,
    currentSession,
    loading,
    error,
    fetchSessions,
    createSession,
    switchSession,
    stopSession,
    pauseSession,
    resumeSession,
  } = useSessionStore();

  const [newSessionDialogOpen, setNewSessionDialogOpen] = React.useState(false);
  const [newSessionName, setNewSessionName] = React.useState('');

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleCreateSession = async () => {
    if (!newSessionName.trim()) return;
    
    try {
      await createSession(newSessionName);
      setNewSessionDialogOpen(false);
      setNewSessionName('');
    } catch (error) {
      console.error('Failed to create session:', error);
    }
  };

  const handleSessionAction = async (sessionId: string, action: 'stop' | 'pause' | 'resume') => {
    try {
      switch (action) {
        case 'stop':
          await stopSession(sessionId);
          break;
        case 'pause':
          await pauseSession(sessionId);
          break;
        case 'resume':
          await resumeSession(sessionId);
          break;
      }
    } catch (error) {
      console.error(`Failed to ${action} session:`, error);
    }
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6">Sessions</Typography>
        <Button
          variant="contained"
          color="primary"
          startIcon={<AddIcon />}
          onClick={() => setNewSessionDialogOpen(true)}
        >
          New Session
        </Button>
      </Box>

      {loading && <LinearProgress />}
      
      {error && (
        <Typography color="error" mb={2}>
          {error}
        </Typography>
      )}

      <List>
        {sessions.map((session) => (
          <Card
            key={session.session_id}
            variant="outlined"
            sx={{
              mb: 1,
              border: currentSession?.session_id === session.session_id
                ? '2px solid primary.main'
                : undefined
            }}
          >
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Box flex={1}>
                  <Typography variant="h6">{session.name}</Typography>
                  <Typography variant="body2" color="textSecondary">
                    Status: {session.state}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Created: {new Date(session.created_at).toLocaleString()}
                  </Typography>
                </Box>

                <Box>
                  {session.state === 'RUNNING' && (
                    <IconButton
                      onClick={() => handleSessionAction(session.session_id, 'pause')}
                      title="Pause Session"
                    >
                      <PauseIcon />
                    </IconButton>
                  )}
                  
                  {session.state === 'PAUSED' && (
                    <IconButton
                      onClick={() => handleSessionAction(session.session_id, 'resume')}
                      title="Resume Session"
                    >
                      <PlayArrowIcon />
                    </IconButton>
                  )}
                  
                  <IconButton
                    onClick={() => handleSessionAction(session.session_id, 'stop')}
                    title="Stop Session"
                    color="error"
                  >
                    <StopIcon />
                  </IconButton>
                </Box>
              </Box>

              <SessionResourceMonitor
                resourceUsage={session.resource_usage}
                state={session.state}
              />

              {session.error_message && (
                <Typography color="error" mt={1}>
                  Error: {session.error_message}
                </Typography>
              )}

              {currentSession?.session_id !== session.session_id && (
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => switchSession(session.session_id)}
                  sx={{ mt: 1 }}
                >
                  Switch to this session
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
      </List>

      <Dialog
        open={newSessionDialogOpen}
        onClose={() => setNewSessionDialogOpen(false)}
      >
        <DialogTitle>Create New Session</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Session Name"
            fullWidth
            value={newSessionName}
            onChange={(e) => setNewSessionName(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNewSessionDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleCreateSession} color="primary">
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};