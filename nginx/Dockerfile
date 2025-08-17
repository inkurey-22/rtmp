FROM alfg/nginx-rtmp:latest

# Copy the provided nginx.conf into the image. This avoids host bind-mount permission issues
COPY nginx.conf /etc/nginx/nginx.conf

# Keep entrypoint/command from base image
