#!/bin/bash
set -e

echo "🚀 Starting Flask Application..."

# ============================================
# Wireguard Setup (if enabled)
# ============================================
if [ "$ENABLE_WIREGUARD" = "true" ] || [ "$ENABLE_WIREGUARD" = "1" ]; then
    echo "🔒 Wireguard enabled - setting up VPN connection..."
    
    WG_CONFIG_PATH="/etc/wireguard/wg0.conf"
    
    # Option 1: Base64-encoded full config
    if [ -n "$WG_CONFIG_BASE64" ]; then
        echo "📝 Creating config from WG_CONFIG_BASE64..."
        echo "$WG_CONFIG_BASE64" | base64 -d > "$WG_CONFIG_PATH"
    
    # Option 2: Individual environment variables
    elif [ -n "$WG_PRIVATE_KEY" ] && [ -n "$WG_PEER_PUBLIC_KEY" ] && [ -n "$WG_PEER_ENDPOINT" ]; then
        echo "📝 Creating config from environment variables..."
        cat > "$WG_CONFIG_PATH" << EOF
[Interface]
Address = ${WG_ADDRESS}
PrivateKey = ${WG_PRIVATE_KEY}

[Peer]
PublicKey = ${WG_PEER_PUBLIC_KEY}
Endpoint = ${WG_PEER_ENDPOINT}
AllowedIPs = ${WG_ALLOWED_IPS}
PersistentKeepalive = ${WG_PERSISTENT_KEEPALIVE}
EOF
    else
        echo "❌ ERROR: Wireguard enabled but no config provided!"
        echo "Provide either:"
        echo "  - WG_CONFIG_BASE64 (full config base64-encoded)"
        echo "  - Or: WG_PRIVATE_KEY, WG_PEER_PUBLIC_KEY, WG_PEER_ENDPOINT"
        exit 1
    fi
    
    # Set correct permissions
    chmod 600 "$WG_CONFIG_PATH"
    
    # Start wireguard interface
    echo "🌐 Starting wireguard interface wg0..."
    wg-quick up "$WG_CONFIG_PATH" || {
        echo "❌ Failed to start wireguard interface"
        # Show config for debugging (without private key)
        echo "Config (sanitized):"
        grep -v "PrivateKey" "$WG_CONFIG_PATH" || true
        exit 1
    }
    
    # Show wireguard status (without private key)
    echo "✅ Wireguard connection established:"
    wg show wg0 | grep -v "private key" || wg show wg0
    
    # Add cleanup on exit
    trap 'echo "🔒 Shutting down wireguard..."; wg-quick down wg0 2>/dev/null || true' EXIT
else
    echo "ℹ️  Wireguard disabled (set ENABLE_WIREGUARD=true to enable)"
fi

# Set Flask app
export FLASK_APP=app:app

# Change to flask_module directory
cd /home/src/flask_module

# Check if database exists
DB_FILE=""
if [ "$ENVIRONMENT_NAME" = "production" ]; then
    DB_FILE="instance/prod.db"
else
    DB_FILE="instance/dev.db"
fi

echo "📍 Database path: $DB_FILE"

# Step 1: Always run init_db.py (safe mode - adds missing columns)
echo "📦 Initializing database (safe mode - preserves existing data)..."
cd /home/src
python3 init_db.py
echo "✅ Database initialized!"

# Step 2: Check and apply migrations (if database has migration history)
if [ -f "$DB_FILE" ]; then
    echo "📊 Checking for pending migrations..."
    cd /home/src/flask_module
    
    # Check if migrations folder exists
    if [ ! -d "migrations" ]; then
        echo "⚠️  No migrations folder found, skipping migration check"
    else
        # Check if there are pending migrations
        PENDING=$(flask db current 2>&1 || echo "no_migrations")
        
        if echo "$PENDING" | grep -q "no_migrations\|Can't locate revision"; then
            echo "⚠️  No migration history found. Stamping current state..."
            flask db stamp head
            echo "✅ Database stamped with current schema!"
        else
            echo "📋 Current migration: $(flask db current 2>/dev/null || echo 'unknown')"
            
            # Try to upgrade
            echo "🔄 Applying pending migrations..."
            flask db upgrade 2>&1 | tee /tmp/migration.log
            
            if [ $? -eq 0 ]; then
                echo "✅ Database migrations applied successfully!"
            else
                echo "⚠️  Migration upgrade had issues, checking if already up to date..."
                if grep -q "Target database is not up to date" /tmp/migration.log; then
                    echo "🔄 Stamping to head..."
                    flask db stamp head
                    echo "✅ Database is now up to date!"
                elif grep -q "already exists" /tmp/migration.log; then
                    echo "✅ Database schema is already up to date!"
                else
                    echo "❌ Migration failed! Check logs above."
                    # Don't exit - let the app start, admin can fix manually
                fi
            fi
        fi
    fi
fi

# Start Gunicorn
echo "🌐 Starting Gunicorn on port 5000..."
cd /home/src
exec gunicorn \
    --bind 0.0.0.0:5000 \
    flask_module.app:app \
    --workers 3 \
    --threads 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info