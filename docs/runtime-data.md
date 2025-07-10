# Runtime Data Management

## Overview

The API Assistant uses **runtime data artifacts** that can be updated independently of the application code. These artifacts include:

- **API Specifications**: OpenAPI specs and summaries
- **API Guidelines**: Authentication and usage guidelines

**Note**: Application logs are handled separately by the logging configuration system and are stored in `/var/log/api-assistant/`.

## Architecture

### **Hybrid Loading Strategy**

The application uses a **fallback approach** for loading runtime data:

1. **External Data** (Priority): Load from external paths
2. **Package-Embedded** (Fallback): Load from within the package

### **External Data Locations**

#### **Development Environment**
```
integration_assistant/
├── data/
│   ├── api_specs/
│   │   ├── api_summaries.yaml
│   │   └── ecommerce_api.yaml
```

#### **Production Environment**
```
/var/lib/api-assistant/
├── api_specs/
│   ├── api_summaries.yaml
│   └── ecommerce_api.yaml

/var/log/api-assistant/           # Application logs (handled by logging config)
└── app.log                      # Structured JSON logs with rotation
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_SPECS_PATH` | `/var/lib/api-assistant/api_specs` | Path to API specifications |

## Benefits

### **✅ Production Advantages**
- **No container rebuilds**: Update API specs without rebuilding
- **Environment flexibility**: Different specs per environment
- **Smaller containers**: Runtime data not baked into image
- **Version independence**: API specs not tied to app version
- **Multi-tenant support**: Different data per deployment

### **✅ Development Advantages**
- **Local customization**: Override with local `data/` directory
- **Easy testing**: Test with different API specs
- **Version control**: Track data changes separately from code

## Usage Examples

### **Development**
```bash
# Use local data directory
./data/api_specs/api_summaries.yaml

# Or set environment variable
API_SPECS_PATH=./custom_specs python -m api_assistant.server
```

### **Production**
```bash
# Mount external data
docker run -v /host/api-specs:/var/lib/api-assistant/api_specs api-assistant

# Or use environment variables
docker run -e API_SPECS_PATH=/custom/path api-assistant
```

### **Kubernetes**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-assistant-data
data:
  api_summaries.yaml: |
    - title: My API
      description: Custom API specification
---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: api-assistant
        volumeMounts:
        - name: api-data
          mountPath: /var/lib/api-assistant/api_specs
      volumes:
      - name: api-data
        configMap:
          name: api-assistant-data
```

## Migration from Package-Embedded

The application automatically falls back to package-embedded data if external data is not found, ensuring backward compatibility.

## Best Practices

1. **Version your data**: Use semantic versioning for API specs
2. **Validate data**: Ensure YAML/JSON is valid before deployment
3. **Backup data**: Keep backups of runtime data
4. **Monitor changes**: Track when data is updated
5. **Test updates**: Validate new specs before production deployment 