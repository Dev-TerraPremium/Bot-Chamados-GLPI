FROM golang:1.26-alpine AS builder

WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/whatsapp-connector .

FROM alpine:3.22

RUN apk add --no-cache ca-certificates tzdata \
    && adduser -D -h /app appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data

WORKDIR /app
COPY --from=builder /out/whatsapp-connector /app/whatsapp-connector

USER appuser
ENV WHATSAPP_STORE_PATH=/data/store.db

CMD ["/app/whatsapp-connector"]
