FROM node:20

# Install Python
RUN apt-get update && apt-get install -y python3 python3-pip

# Set working directory
WORKDIR /app

# Install Node dependencies
COPY package*.json ./
RUN npm install

# Install Python dependencies
COPY scraper/requirements.txt ./scraper/
RUN pip3 install -r scraper/requirements.txt --break-system-packages

# Copy all files
COPY . .

# Start server
CMD ["npm", "start"]
```

Also update `requirements.txt` to make sure it has everything:
```
requests
feedparser
beautifulsoup4
python-dotenv