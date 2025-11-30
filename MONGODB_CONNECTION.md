# MongoDB Connection Guide

## Connection Methods

### 1. From Host Machine (using mongosh)

```bash
# Connect to MongoDB running in Docker container
mongosh "mongodb://admin:root@localhost:27017/test?authSource=admin"
```

Or interactively:
```bash
mongosh "mongodb://admin:root@localhost:27017/test?authSource=admin"
```

### 2. From Container Bash

```bash
# Enter the container
docker exec -it mongodb_db bash

# Connect using mongosh
mongosh -u admin -p root --authenticationDatabase admin
```

### 3. Execute Commands Directly

```bash
# Run a single command
docker exec mongodb_db mongosh -u admin -p root --authenticationDatabase admin --eval "db.adminCommand('ping')"

# Connect to a specific database
docker exec mongodb_db mongosh -u admin -p root --authenticationDatabase admin test --eval "db.books.find().pretty()"
```

### 4. Connection String Format

```
mongodb://admin:root@mongodb:27017/test?replicaSet=rs0&authSource=admin
```

**Parameters:**
- `admin:root` - Username and password
- `mongodb:27017` - Host and port (use `localhost:27017` from host, `mongodb:27017` from other containers)
- `test` - Database name
- `replicaSet=rs0` - Replica set name
- `authSource=admin` - Authentication database

## Common Commands

### Check Connection
```bash
docker exec mongodb_db mongosh -u admin -p root --authenticationDatabase admin --eval "db.adminCommand('ping')"
```

### List Databases
```bash
docker exec mongodb_db mongosh -u admin -p root --authenticationDatabase admin --eval "show dbs"
```

### Use a Database
```bash
docker exec mongodb_db mongosh -u admin -p root --authenticationDatabase admin test
```

### Query Collections
```bash
docker exec mongodb_db mongosh -u admin -p root --authenticationDatabase admin test --eval "db.books.find().pretty()"
```

### Check Replica Set Status
```bash
docker exec mongodb_db mongosh -u admin -p root --authenticationDatabase admin --eval "rs.status()"
```

## Troubleshooting

If you get "Authentication failed":
1. Ensure the admin user exists: `docker exec mongodb_db mongosh --eval "db.getUsers()"`
2. If user doesn't exist, create it (see docker-compose.local.yml initialization script)
3. Make sure you're using `--authenticationDatabase admin` or `authSource=admin` in connection string

If you get "Connection refused":
1. Check if container is running: `docker ps | grep mongodb`
2. Check MongoDB logs: `docker logs mongodb_db`
3. Ensure MongoDB is bound to all interfaces: `--bind_ip_all` in command

