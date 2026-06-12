# Kényelmi parancsok — opcionális (a sima `docker compose` is elég)
.PHONY: up down logs ps psql reset clean

up:        ## Build + indítás háttérben
	docker compose up -d --build

down:      ## Leállítás (adat marad)
	docker compose down

reset:     ## Teljes reset (kötetek törlése is)
	docker compose down -v

logs:      ## ETL pipeline logok követése
	docker compose logs -f etl

ps:        ## Konténer-állapotok
	docker compose ps

psql:      ## Belépés a tárház adatbázisba
	docker compose exec postgres psql -U dataeng -d warehouse

clean: reset ## Alias a reset-re
	@echo "Kornyezet teljesen torolve."
