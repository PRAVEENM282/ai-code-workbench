ARG NODE_IMAGE
ARG NGINX_IMAGE
FROM ${NODE_IMAGE} AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build

FROM ${NGINX_IMAGE} AS runtime
ARG FRONTEND_CONTAINER_PORT
ENV FRONTEND_CONTAINER_PORT=${FRONTEND_CONTAINER_PORT}
COPY --from=build --chown=nginx:nginx /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/nginx.conf
COPY --chown=nginx:nginx frontend/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --chown=nginx:nginx frontend/docker-entrypoint.d/40-runtime-config.sh /docker-entrypoint.d/40-runtime-config.sh
RUN chmod 0555 /docker-entrypoint.d/40-runtime-config.sh \
    && mkdir -p /var/cache/nginx \
    && chown -R nginx:nginx /var/cache/nginx /var/run /usr/share/nginx/html
ENV NGINX_ENVSUBST_FILTER="FRONTEND_CONTAINER_PORT|WORKBENCH_SERVICE__PORT"
ENV NGINX_ENVSUBST_OUTPUT_DIR="/tmp"
EXPOSE ${FRONTEND_CONTAINER_PORT}
USER nginx
CMD ["nginx", "-g", "daemon off;"]
