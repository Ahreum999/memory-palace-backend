FROM node:20

RUN apt-get update && apt-get install -y python3 python3-pip

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY scraper/requirements.txt ./scraper/
RUN pip3 install -r scraper/requirements.txt --break-system-packages

COPY . .

CMD ["npm", "start"]