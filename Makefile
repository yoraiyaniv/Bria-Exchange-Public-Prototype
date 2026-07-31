.PHONY: start stop restart status logs

start:
	@echo "Removing stale bridges..."
	@for br in $$(ip link show type bridge | awk -F'[ :]+' '/br-/{print $$2}'); do \
		state=$$(ip link show $$br | grep -o 'state [A-Z]*' | awk '{print $$2}'); \
		if [ "$$state" = "DOWN" ]; then \
			echo "  Removing stale bridge $$br"; \
			sudo ip link delete $$br 2>/dev/null || true; \
		fi; \
	done
	docker compose up -d
	@echo "Done. Run 'make status' to check."

stop:
	@echo "Stopping containers..."
	@for name in $$(docker compose ps -q 2>/dev/null); do \
		pid=$$(sudo docker inspect $$name --format '{{.State.Pid}}' 2>/dev/null); \
		if [ -n "$$pid" ] && [ "$$pid" != "0" ]; then \
			sudo kill -9 $$pid 2>/dev/null || true; \
		fi; \
	done
	@sleep 2
	@sudo docker ps -aq --filter "label=com.docker.compose.project=bria-exchange" | xargs -r sudo docker rm -f 2>/dev/null || true
	@docker network prune -f 2>/dev/null || true
	@echo "Done."

restart: stop start

status:
	@docker compose ps
	@echo ""
	@printf "Frontend: "; curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:3000/ || echo "UNREACHABLE"

logs:
	docker compose logs -f --tail=50
