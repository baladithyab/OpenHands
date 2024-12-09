# OpenHands Testing Examples

This directory contains example scripts to test various OpenHands features.

## Multi-Session and Cost Tracking Test

The `multi_session_test.py` script demonstrates:
1. Multi-session management
2. Resource monitoring
3. Cost tracking
4. Session operations

### Running the Test

1. Make sure OpenHands is installed and configured:
```bash
# From the repository root
poetry install
```

2. Run the test script:
```bash
poetry run python examples/multi_session_test.py
```

### What the Test Does

1. **Session Management**
   - Creates multiple sessions
   - Tests session operations (pause, resume, stop)
   - Monitors session states

2. **Cost Tracking**
   - Sets cost limits and warning thresholds
   - Simulates LLM usage with different models
   - Generates cost summaries
   - Demonstrates cost limit enforcement

3. **Resource Monitoring**
   - Tracks CPU, memory, and disk usage
   - Monitors container counts
   - Shows real-time resource stats

### Expected Output

The script will output:
1. Session creation and operations
2. Cost warnings and limit violations
3. Usage summaries for each session
4. Resource usage statistics
5. Final session states

### Troubleshooting

1. **Docker Issues**
   - Make sure Docker is running
   - Check Docker permissions
   - Verify container access

2. **Permission Issues**
   - Check file permissions in cache directory
   - Verify Docker socket access

3. **Resource Issues**
   - Ensure enough system resources
   - Check Docker resource limits