FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=""
ARG VITE_ADMIN_KEY=change-me
ARG VITE_ZITADEL_AUTHORITY=http://localhost:8088
ARG VITE_ZITADEL_CLIENT_ID=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_ADMIN_KEY=$VITE_ADMIN_KEY
ENV VITE_ZITADEL_AUTHORITY=$VITE_ZITADEL_AUTHORITY
ENV VITE_ZITADEL_CLIENT_ID=$VITE_ZITADEL_CLIENT_ID
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
