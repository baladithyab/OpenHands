import React from 'react';
import {
  Box,
  LinearProgress,
  Typography,
  useTheme,
} from '@mui/material';
import { ResourceUsage } from '../../stores/sessionStore';

interface Props {
  resourceUsage: ResourceUsage;
  state: string;
}

export const SessionResourceMonitor: React.FC<Props> = ({ resourceUsage, state }) => {
  const theme = useTheme();

  const getColorForUsage = (percent: number) => {
    if (percent >= 90) return theme.palette.error.main;
    if (percent >= 70) return theme.palette.warning.main;
    return theme.palette.success.main;
  };

  const formatBytes = (mb: number) => {
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(1)} GB`;
    }
    return `${mb.toFixed(1)} MB`;
  };

  return (
    <Box mt={2}>
      <Typography variant="subtitle2" gutterBottom>
        Resource Usage
      </Typography>

      <Box mb={1}>
        <Box display="flex" justifyContent="space-between">
          <Typography variant="body2">CPU</Typography>
          <Typography variant="body2">
            {resourceUsage.cpu_percent.toFixed(1)}%
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={resourceUsage.cpu_percent}
          sx={{
            '& .MuiLinearProgress-bar': {
              backgroundColor: getColorForUsage(resourceUsage.cpu_percent),
            },
          }}
        />
      </Box>

      <Box mb={1}>
        <Box display="flex" justifyContent="space-between">
          <Typography variant="body2">Memory</Typography>
          <Typography variant="body2">
            {formatBytes(resourceUsage.memory_mb)}
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={(resourceUsage.memory_mb / 1024) * 100} // Assuming 1GB limit
          sx={{
            '& .MuiLinearProgress-bar': {
              backgroundColor: getColorForUsage((resourceUsage.memory_mb / 1024) * 100),
            },
          }}
        />
      </Box>

      <Box mb={1}>
        <Box display="flex" justifyContent="space-between">
          <Typography variant="body2">Disk</Typography>
          <Typography variant="body2">
            {formatBytes(resourceUsage.disk_mb)}
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={(resourceUsage.disk_mb / 2048) * 100} // Assuming 2GB limit
          sx={{
            '& .MuiLinearProgress-bar': {
              backgroundColor: getColorForUsage((resourceUsage.disk_mb / 2048) * 100),
            },
          }}
        />
      </Box>

      <Box display="flex" justifyContent="space-between">
        <Typography variant="body2">Containers</Typography>
        <Typography variant="body2">
          {resourceUsage.container_count} / 3
        </Typography>
      </Box>

      <Typography variant="caption" color="textSecondary">
        Last updated: {new Date(resourceUsage.last_updated).toLocaleString()}
      </Typography>
    </Box>
  );
};