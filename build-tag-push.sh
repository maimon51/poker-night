echo build
docker-compose build 
echo tag
docker tag poker-night-bot:latest maimon51/webapps:pokerbot 
echo push
docker push maimon51/webapps:pokerbot
