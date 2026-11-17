
PYTHON_IMAGE := python:3.12-slim

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

# Gamerule variable names mapped to their Minecraft command names.
GAMERULE_MAP := \
	COMMAND_BLOCK_OUTPUT:commandblockoutput \
	COMMAND_BLOCKS_ENABLED:commandblocksenabled \
	DO_DAYLIGHT_CYCLE:dodaylightcycle \
	DO_ENTITY_DROPS:doentitydrops \
	DO_FIRE_TICK:dofiretick \
	DO_IMMEDIATE_RESPAWN:doimmediaterespawn \
	DO_INSOMNIA:doinsomnia \
	DO_LIMITED_CRAFTING:dolimitedcrafting \
	DO_MOB_LOOT:domobloot \
	DO_MOB_SPAWNING:domobspawning \
	DO_TILE_DROPS:dotiledrops \
	DO_WEATHER_CYCLE:doweathercycle \
	DROWNING_DAMAGE:drowningdamage \
	FALL_DAMAGE:falldamage \
	FIRE_DAMAGE:firedamage \
	FREEZE_DAMAGE:freezedamage \
	FUNCTION_COMMAND_LIMIT:functioncommandlimit \
	KEEP_INVENTORY:keepinventory \
	MAX_COMMAND_CHAIN_LENGTH:maxcommandchainlength \
	MOB_GRIEFING:mobgriefing \
	NATURAL_REGENERATION:naturalregeneration \
	PLAYERS_SLEEPING_PERCENTAGE:playerssleepingpercentage \
	PLAYER_WAYPOINTS:playerwaypoints \
	PROJECTILES_CAN_BREAK_BLOCKS:projectilescanbreakblocks \
	PVP:pvp \
	RANDOM_TICK_SPEED:randomtickspeed \
	RECIPES_UNLOCK:recipesunlock \
	RESPAWN_BLOCKS_EXPLODE:respawnblocksexplode \
	SEND_COMMAND_FEEDBACK:sendcommandfeedback \
	SHOW_BORDER_EFFECT:showbordereffect \
	SHOW_COORDINATES:showcoordinates \
	SHOW_DAYS_PLAYED:showdaysplayed \
	SHOW_DEATH_MESSAGES:showdeathmessages \
	SHOW_RECIPE_MESSAGES:showrecipemessages \
	SHOW_TAGS:showtags \
	SPAWN_RADIUS:spawnradius \
	TNT_EXPLODES:tntexplodes \
	TNT_EXPLOSION_DROP_DECAY:tntexplosiondropdecay

# Generate commands only for variables that have nonempty values.
GAMERULE_COMMANDS = $(foreach pair,$(GAMERULE_MAP),$(if $(strip $($(word 1,$(subst :, ,$(pair))))),gamerule $(word 2,$(subst :, ,$(pair))) $($(word 1,$(subst :, ,$(pair))))|))

.PHONY: create-server setup-playit start stop start-server stop-server configure-gamerules

setup-playit:
	@test -n "$(TOKEN)" || (echo "ERROR: specify TOKEN=<playit-secret-key>"; exit 1)
	docker run --rm \
		-v "$(CURDIR):/workspace" \
		-w /workspace \
		-e TOKEN="$(TOKEN)" \
		python:3.12-slim \
		python scripts/setup-playit.py
	docker compose config --quiet
	docker compose up -d --force-recreate playit
	@echo "Playit agent configured and started."

create-server:
	@test -n "$(NAME)" || (echo "ERROR: specify NAME=<server-name>"; exit 1)
	@test -n "$(TOKEN)" || (echo "ERROR: specify TOKEN=<nethernet-token>"; exit 1)

	@echo "Generating Compose services for $(NAME)..."
	docker run --rm \
		-v "$(CURDIR):/workspace" \
		-w /workspace \
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
		$(PYTHON_IMAGE) \
		sh -ec 'pip install --quiet ruamel.yaml && python scripts/create-server.py'

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

configure-gamerules:
	@test -n "$(NAME)" || (echo "ERROR: specify NAME=<server-name>"; exit 1)
	@commands='$(GAMERULE_COMMANDS)'; \
	if [ -z "$$commands" ]; then \
		echo "ERROR: specify at least one gamerule."; \
		exit 1; \
	fi; \
	if [ "$$(docker inspect -f '{{.State.Running}}' "$(NAME)" 2>/dev/null)" != "true" ]; then \
		echo "ERROR: server '$(NAME)' is not running."; \
		exit 1; \
	fi; \
	commands="$${commands%|}"; \
	echo "Configuring the following gamerules for $(NAME):"; \
	printf '%s\n' "$$commands" | tr '|' '\n'; \
	printf '%s\n\020\021' "$$commands" | tr '|' '\n' | docker attach --sig-proxy=false "$(NAME)"