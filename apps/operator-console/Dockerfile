FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY index.html postcss.config.js tailwind.config.js tsconfig.json vite.config.ts ./
COPY src ./src

EXPOSE 3000

CMD ["npm", "run", "dev"]
