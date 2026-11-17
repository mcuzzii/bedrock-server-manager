DIFFICULTY ?= normal
GAMEMODE ?= survival
FORCE_GAMEMODE ?= false
MAX_PLAYERS ?= 20
VIEW_DISTANCE ?= 32
TICK_DISTANCE ?= 4
ALLOW_CHEATS ?= false
ALLOW_LIST ?= false
PLAYER_IDLE_TIMEOUT ?= 30
DEFAULT_PLAYER_PERMISSION_LEVEL ?= member
TEXTUREPACK_REQUIRED ?= false
CONTENT_LOG_FILE_ENABLED ?= false
MAX_THREADS ?= 0
LEVEL_SEED ?=

.PHONY: create-server setup-playit start stop start-server stop-server

setup-playit:
	@test -n "$(TOKEN)" || (echo "ERROR: specify TOKEN=<playit-secret-key>"; exit 1)

	docker compose run --rm --no-deps \
		-e TOKEN="$(TOKEN)" \
		setup-playit-tool

	docker compose config --quiet
	docker compose up -d --force-recreate playit
	@echo "Playit agent configured and started."

create-server:
	@test -n "$(NAME)" || (echo "ERROR: specify NAME=<server-name>"; exit 1)
	@test -n "$(TOKEN)" || (echo "ERROR: specify TOKEN=<nethernet-token>"; exit 1)

	@echo "Generating Compose services for $(NAME)..."
	docker compose run --rm --no-deps \
		-e SERVER_NAME="$(NAME)" \
		-e NETHERNET_TOKEN="$(TOKEN)" \
		-e LEVEL_NAME="$(NAME)-world" \
		-e DIFFICULTY="$(DIFFICULTY)" \
		-e GAMEMODE="$(GAMEMODE)" \
		-e FORCE_GAMEMODE="$(FORCE_GAMEMODE)" \
		-e MAX_PLAYERS="$(MAX_PLAYERS)" \
		-e VIEW_DISTANCE="$(VIEW_DISTANCE)" \
		-e TICK_DISTANCE="$(TICK_DISTANCE)" \
		-e ALLOW_CHEATS="$(ALLOW_CHEATS)" \
		-e ALLOW_LIST="$(ALLOW_LIST)" \
		-e PLAYER_IDLE_TIMEOUT="$(PLAYER_IDLE_TIMEOUT)" \
		-e DEFAULT_PLAYER_PERMISSION_LEVEL="$(DEFAULT_PLAYER_PERMISSION_LEVEL)" \
		-e TEXTUREPACK_REQUIRED="$(TEXTUREPACK_REQUIRED)" \
		-e CONTENT_LOG_FILE_ENABLED="$(CONTENT_LOG_FILE_ENABLED)" \
		-e MAX_THREADS="$(MAX_THREADS)" \
		-e LEVEL_SEED="$(LEVEL_SEED)" \
		create-server-tool

	@echo "Validating generated Compose configuration..."
	docker compose config --quiet

	@echo "Initializing Endstone..."
	docker compose up -d "$(NAME)"

	@echo "Installing Xuidforward..."
	docker compose up -d --force-recreate "$(NAME)-prep"

	@echo "Restarting Endstone to load Xuidforward..."
	docker compose up -d --no-deps --force-recreate "$(NAME)"

	@echo "Starting Playit and Waterdog..."
	docker compose up -d playit "$(NAME)-waterdog"

	@echo ""
	@echo "Server $(NAME) has been provisioned."
	@echo "Endstone: $(NAME)"
	@echo "Waterdog: $(NAME)-waterdog"
	@echo "Prep:     $(NAME)-prep"

start:
	docker compose up -d

stop:
	docker compose stop

start-server:
	@test -n "$(NAME)" || (echo "ERROR: specify NAME=<server-name>"; exit 1)
	docker compose up -d "$(NAME)-waterdog"

stop-server:
	@test -n "$(NAME)" || (echo "ERROR: specify NAME=<server-name>"; exit 1)
	docker compose stop "$(NAME)-waterdog" "$(NAME)"