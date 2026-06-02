# M-16: digest-pin the base images so a tag re-point can't silently change the
# build. Tags resolved 2026-06-02; refresh via Dependabot.
FROM node:20-alpine@sha256:afdf98210b07b586eb71fa22ba2e432e058e4cd1304d31ed60888755b8c865fb AS build

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

FROM nginx:alpine@sha256:31db9045b34376493fd4fb695d8a8d03bbfffaf6297fcde82d0f925ce2dd329a

LABEL org.opencontainers.image.title="risk-manager-pro-web" \
      org.opencontainers.image.vendor="Faith Group, LLC" \
      org.opencontainers.image.description="Risk Manager Pro React frontend"

COPY --from=build /app/dist /usr/share/nginx/html
# M-16: serve on 8080 so the container can run as the unprivileged nginx user
# (binding <1024 requires root). Production frontend is Azure Static Web Apps;
# this image is for container-based hosting and local parity.
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen 8080;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF

# M-16: run as non-root. Redirect the master pid to a writable path, make the
# cache/log dirs writable by the nginx user, and drop the top-level `user`
# directive (only honored when the master runs as root).
RUN sed -i 's!/var/run/nginx.pid!/tmp/nginx.pid!' /etc/nginx/nginx.conf \
    && sed -i '/^user  nginx;/d' /etc/nginx/nginx.conf \
    && chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx

USER nginx

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q --spider http://localhost:8080/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
