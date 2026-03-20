FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL=""
ARG VITE_AZURE_AD_CLIENT_ID=""
ARG VITE_AZURE_AD_AUTHORITY=""
ARG VITE_AZURE_AD_REDIRECT_URI=""
ARG VITE_API_SCOPE=""

RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
