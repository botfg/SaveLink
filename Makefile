run:
	docker run -it -d --env-file .env --restart=unless-stopped --name save_link save_link_image
stop:
	docker stop save_link
attach:
	docker attach save_link
dell:
	docker rm save_link