
# Add current ping data to repository data
./scripts/push-server-data.sh

# Push data via git
(
	set -e
	cd remote_data/
	git checkout incoming-data-$HOSTNAME
	git add .
	git commit -m "Autocommit data $(date +"%Y-%m-%d %a")"
	git push
)
