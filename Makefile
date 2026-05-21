.PHONY: dashboard-install dashboard-build dashboard-dev desktop-icons desktop-build desktop-install desktop-quit

dashboard-install:
	cd dashboard-ui && npm install

dashboard-build:
	cd dashboard-ui && npm run build

dashboard-dev:
	cd dashboard-ui && npm run dev

desktop-icons:
	APP_NAME='Security Observatory' APP_SLUG='security-observatory' ./scripts/desktop-icons.sh

desktop-build:
	./scripts/desktop-build.sh

desktop-install:
	./scripts/desktop-install.sh

desktop-quit:
	./scripts/desktop-quit.sh
