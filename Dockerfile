# STAGE 1: Build
FROM golang:1.23-alpine AS builder

WORKDIR /app

# Download dependencies first (caching layers)
COPY go.mod go.sum ./
RUN go mod download

# Copy source and build
COPY . .
# CGO_ENABLED=0 creates a statically linked binary (no dependency on OS libs)
RUN CGO_ENABLED=0 GOOS=linux go build -o lifeos-api .

# STAGE 2: Run (Tiny Image)
FROM gcr.io/distroless/static-debian12

WORKDIR /

# Copy the binary from builder
COPY --from=builder /app/lifeos-api /lifeos-api

# Expose port (must match the port in main.go)
EXPOSE 8080

USER nonroot:nonroot

CMD ["/lifeos-api"]