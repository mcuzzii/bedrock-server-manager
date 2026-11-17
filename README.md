## Make a Playit Agent

```bash
make setup-playit TOKEN='your-playit-secret-key'
```

## Create a New Server

```bash
make create-server \
    NAME=your-server-name \
    TOKEN='your-nethernet-token-key' \
    DIFFICULTY=normal \
    GAMEMODE=survival \
    MAX_PLAYERS=10 \
    VIEW_DISTANCE=32 \
    TICK_DISTANCE=4 \
    ALLOW_CHEATS=false \
    ALLOW_LIST=false \
    PLAYER_IDLE_TIMEOUT=0
```

This turns the server on subsequently as well. You can join the server at the specified playit IP address.

## Turn Off a Server

```bash
make stop-server NAME=your-server-name
```

## Turn On a Server

```bash
make start-server NAME=your-server-name
```

## Turn Off All Services

```bash
make stop
```