# 📋 Ollama Migration Guide - Move Models to /mnt/models

## 🎯 Current Situation

### ✅ Current Ollama Configuration

**Current Location**: `/usr/share/ollama/.ollama/`
- **Size**: 5.6GB
- **Models**: qwen2.5:7b-instruct, llama3.2:1b
- **Service**: Running (PID 1414)

**New Location**: `/mnt/models/ollama/`
- **Space Available**: 870GB free
- **Purpose**: Dedicated model storage
- **Status**: Directory exists, empty

## 🚀 Migration Plan

### Phase 1: Stop Ollama Service

```bash
# Stop the Ollama service
sudo systemctl stop ollama

# Verify it's stopped
systemctl status ollama | grep "Active:"
# Should show: Active: inactive (dead)
```

### Phase 2: Move Existing Models

```bash
# Copy models to new location
sudo cp -r /usr/share/ollama/.ollama/models/* /mnt/models/ollama/

# Verify copy
ls -la /mnt/models/ollama/
# Should show: blobs, manifests, models directories
```

### Phase 3: Configure Ollama for New Location

```bash
# Edit Ollama service configuration
sudo nano /etc/systemd/system/ollama.service

# Find the ExecStart line and add OLLAMA_MODELS environment variable
# Change from:
# ExecStart=/usr/local/bin/ollama serve
# To:
ExecStart=/usr/local/bin/ollama serve --model /mnt/models/ollama

# Save and exit (Ctrl+X, Y, Enter)
```

**Alternative Configuration Method**:
```bash
# Create environment file
sudo mkdir -p /etc/ollama
sudo nano /etc/ollama/ollama.env

# Add this line:
OLLAMA_MODELS=/mnt/models/ollama

# Save and exit
```

### Phase 4: Update Permissions

```bash
# Ensure Ollama user can access the new location
sudo chown -R ollama:ollama /mnt/models/ollama/

# Set proper permissions
sudo chmod -R 755 /mnt/models/ollama/
```

### Phase 5: Reload and Restart Service

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Start Ollama service
sudo systemctl start ollama

# Verify it's running
systemctl status ollama | head -10
```

### Phase 6: Verify Migration

```bash
# Check models are loaded
ollama list

# Test inference
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:7b-instruct",
  "prompt": "Test response"
}' | head -5
```

## 📋 Detailed Step-by-Step Guide

### Step 1: Check Current Models

```bash
echo "📊 Current Ollama Models:"
ollama list
echo ""
echo "📁 Current Model Directory:"
ls -lh /usr/share/ollama/.ollama/models/
```

### Step 2: Stop Ollama Service

```bash
echo "🛑 Stopping Ollama service..."
sudo systemctl stop ollama
echo "✅ Ollama service stopped"
```

### Step 3: Create Backup (Optional but Recommended)

```bash
echo "💾 Creating backup..."
sudo tar -czvf /tmp/ollama_models_backup_$(date +%Y%m%d).tar.gz /usr/share/ollama/.ollama/models/
echo "✅ Backup created at /tmp/ollama_models_backup_*.tar.gz"
```

### Step 4: Copy Models to New Location

```bash
echo "📦 Copying models to /mnt/models/ollama/..."
sudo cp -r /usr/share/ollama/.ollama/models/* /mnt/models/ollama/
echo "✅ Models copied"
```

### Step 5: Verify Copy

```bash
echo "🔍 Verifying copy..."
ls -lh /mnt/models/ollama/
echo ""
echo "Original directory:"
ls -lh /usr/share/ollama/.ollama/models/
```

### Step 6: Configure Ollama Service

```bash
echo "⚙️ Configuring Ollama service..."
sudo sed -i 's|ExecStart=/usr/local/bin/ollama serve|ExecStart=/usr/local/bin/ollama serve --model /mnt/models/ollama|' /etc/systemd/system/ollama.service
echo "✅ Configuration updated"
```

### Step 7: Set Permissions

```bash
echo "🔐 Setting permissions..."
sudo chown -R ollama:ollama /mnt/models/ollama/
sudo chmod -R 755 /mnt/models/ollama/
echo "✅ Permissions set"
```

### Step 8: Reload and Restart

```bash
echo "🔄 Reloading systemd..."
sudo systemctl daemon-reload
echo "✅ Systemd reloaded"

echo "🚀 Starting Ollama..."
sudo systemctl start ollama
echo "✅ Ollama started"
```

### Step 9: Verify Everything Works

```bash
echo "🧪 Testing Ollama..."
ollama list
echo ""
echo "Testing inference..."
curl -s http://localhost:11434/api/generate -d '{"model":"qwen2.5:7b-instruct","prompt":"Hello"}' | grep -A2 '"response"'
```

### Step 10: Clean Up (Optional)

```bash
# Remove old models (after verification)
# sudo rm -rf /usr/share/ollama/.ollama/models/*
# echo "✅ Old models removed"
```

## 🎯 Configuration File Reference

### Ollama Service File

**Location**: `/etc/systemd/system/ollama.service`

**Before**:
```ini
[Service]
ExecStart=/usr/local/bin/ollama serve
```

**After**:
```ini
[Service]
ExecStart=/usr/local/bin/ollama serve --model /mnt/models/ollama
```

## 📊 Storage Comparison

### Before Migration
```
Location: /usr/share/ollama/.ollama/
- Total Space: 94GB (main drive)
- Used: 5.6GB
- Free: 19GB
- Usage: 6%
```

### After Migration
```
Location: /mnt/models/ollama/
- Total Space: 916GB (dedicated drive)
- Used: 5.6GB
- Free: 870GB
- Usage: 0.6%
```

## ✅ Benefits of Migration

1. **More Space**: 870GB vs 19GB free
2. **Better Organization**: Dedicated drive for models
3. **Easier Management**: Separate from system files
4. **Future-Proof**: Room for many more models
5. **Performance**: Potentially better I/O performance

## ⚠️ Troubleshooting

### Issue: Permission Denied
```bash
# Fix permissions
sudo chown -R ollama:ollama /mnt/models/ollama/
sudo chmod -R 755 /mnt/models/ollama/
```

### Issue: Service Won't Start
```bash
# Check logs
journalctl -u ollama -n 20

# Check configuration
systemctl cat ollama
```

### Issue: Models Not Found
```bash
# Verify models are in correct location
ls -la /mnt/models/ollama/

# Check Ollama can access them
sudo -u ollama ls -la /mnt/models/ollama/
```

## 🎉 Post-Migration Steps

### 1. Update SOA1 Configuration
```yaml
# In home-ai/soa1/config.yaml
# No changes needed - Ollama handles the path
model:
  provider: "ollama"
  base_url: "http://localhost:11434"
  model_name: "qwen2.5:7b-instruct"
```

### 2. Test All Functionality
```bash
# Test SOA1 API
cd /home/ryzen/projects/home-ai/soa1
python3 api.py &

# Test PDF processing
curl -X POST -F "file=@test.pdf" http://localhost:8001/upload-pdf
```

### 3. Document the Change
Update `RemAssist/SERVICES_CONFIG.md`:
```markdown
### Ollama Service

**Model Location**: `/mnt/models/ollama/`
**Configuration**: Custom path via systemd
**Status**: ✅ Migrated to dedicated drive
```

## 📋 Migration Checklist

- [ ] Stop Ollama service
- [ ] Copy models to /mnt/models/ollama/
- [ ] Configure Ollama service
- [ ] Set permissions
- [ ] Reload and restart service
- [ ] Verify models loaded
- [ ] Test inference
- [ ] Update documentation
- [ ] Clean up old models (optional)

## 🎯 Summary

**Current Location**: `/usr/share/ollama/.ollama/` (5.6GB)
**New Location**: `/mnt/models/ollama/` (870GB free)
**Migration Time**: ~5-10 minutes
**Risk Level**: Low
**Benefit**: High

**Recommendation**: Proceed with migration to better utilize our dedicated models drive!

Would you like me to:
1. ✅ **Execute the migration** now
2. ❌ **Keep current setup**
3. 📋 **Show more details** about any step

The migration will free up space on the main drive and provide much more room for additional models! 🚀
