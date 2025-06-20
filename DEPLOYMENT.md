# Deployment Guide - Fly.io

This guide walks you through deploying Claude Logs to fly.io.

## Prerequisites

1. **Install flyctl** (Fly.io CLI):
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Sign up and login to fly.io**:
   ```bash
   flyctl auth signup  # or flyctl auth login
   ```

3. **Set up Supabase project**:
   - Create a free account at [supabase.com](https://supabase.com)
   - Create a new project
   - Get your project URL and service role key from Settings → API
   - Enable Storage in your project dashboard

4. **Export Supabase credentials**:
   ```bash
   export SUPABASE_URL="https://your-project.supabase.co"
   export SUPABASE_SERVICE_KEY="your-service-role-key"
   ```

5. **Verify your fly.io account** (may require payment method for resource allocation)

## Quick Deployment

Use the provided deployment script for automated setup:

```bash
./deploy.sh
```

This script will:
- Create the fly.io app
- Validate Supabase configuration
- Generate and set secure environment variables
- Deploy the application
- Open the deployed app in your browser

## Manual Deployment

If you prefer to deploy manually:

### 1. Create the Application

```bash
flyctl apps create claude-logs
```

### 2. Set Environment Variables

```bash
# Generate a secure secret key
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Set all secrets in fly.io
flyctl secrets set \
    SECRET_KEY="$SECRET_KEY" \
    SUPABASE_URL="$SUPABASE_URL" \
    SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_KEY"
```

### 3. Deploy

```bash
flyctl deploy
```

### 4. Open Application

```bash
flyctl open
```

## Configuration

The application is configured through `fly.toml`:

- **Mode**: Set to `cloud` for upload functionality
- **Storage**: Supabase storage for file uploads
- **Memory**: 512MB (adjustable based on usage)
- **Auto-scaling**: Scales to 0 when not in use
- **Health checks**: Monitors `/health` endpoint

## Environment Variables

| Variable | Value | Description |
|----------|--------|-------------|
| `CLAUDE_MODE` | `cloud` | Enables upload functionality |
| `SUPABASE_URL` | `https://your-project.supabase.co` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | `<service-key>` | Supabase service role key |
| `SUPABASE_BUCKET` | `claude-logs-uploads` | Storage bucket name |
| `MAX_CONTENT_LENGTH` | `52428800` | 50MB upload limit |
| `SESSION_TIMEOUT_HOURS` | `24` | Session cleanup interval |
| `SECRET_KEY` | `<random>` | Flask session security |

## Post-Deployment

### Monitoring

```bash
# View application logs
flyctl logs

# Check application status
flyctl status

# Monitor resource usage
flyctl status --all
```

### Scaling

```bash
# Scale to specific number of instances
flyctl scale count 1

# Scale memory if needed
flyctl scale memory 1024

# Scale CPU if needed  
flyctl scale vm shared-cpu-2x
```

### Accessing the Application

```bash
# Open in browser
flyctl open

# Get application URL
flyctl info
```

### SSH Access

```bash
# SSH into the running container
flyctl ssh console

# Check uploads directory
flyctl ssh console -C "ls -la /app/uploads"
```

## Troubleshooting

### Common Issues

1. **Supabase connection issues**:
   ```bash
   # Check environment variables are set
   flyctl secrets list
   
   # Verify Supabase credentials
   flyctl ssh console -C "env | grep SUPABASE"
   ```

2. **App not starting**:
   ```bash
   flyctl logs
   flyctl status --all
   ```

3. **Upload failures**:
   - Check Supabase bucket exists and permissions are correct
   - Verify service key has storage permissions
   - Check application logs: `flyctl logs`

4. **Storage bucket issues**:
   - Create bucket manually in Supabase dashboard
   - Verify bucket name matches `SUPABASE_BUCKET` environment variable
   - Check storage policies allow service role access

5. **Memory issues**:
   ```bash
   flyctl scale memory 1024  # Scale to 1GB
   ```

### Useful Commands

```bash
# Restart application
flyctl restart

# Deploy specific version
flyctl deploy --image-label v1.0.0

# View application info
flyctl info

# Update secrets
flyctl secrets set SECRET_KEY="new-secret"

# List all apps
flyctl apps list

# Destroy app (careful!)
flyctl apps destroy claude-logs
```

## Security Considerations

- **SECRET_KEY**: Automatically generated secure random key
- **File Validation**: Only JSONL files accepted
- **Size Limits**: 50MB max upload size
- **HTTPS**: Forced HTTPS in production
- **Session Cleanup**: Automatic cleanup of old uploads
- **Non-root User**: Container runs as non-root user

## Cost Optimization

- **Auto-stop**: App scales to 0 when not in use
- **Shared CPU**: Uses cost-effective shared CPU instances
- **Small Volume**: 1GB storage volume (expandable)
- **Efficient Images**: Optimized Docker image with minimal dependencies

## Updates

To update the application:

```bash
# Make your changes locally
git add .
git commit -m "Update application"

# Deploy changes
flyctl deploy

# Monitor deployment
flyctl logs
```

## Support

- **Fly.io Documentation**: https://fly.io/docs/
- **Fly.io Community**: https://community.fly.io/
- **Application Logs**: `flyctl logs`
- **Health Check**: `https://your-app.fly.dev/health`