package main

import (
	"context"
	"log"
	"net/http"
	"os"

	"github.com/jackc/pgx/v5/pgxpool"
)

func main() {
	// 1. Get Config from Environment Variables
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		log.Fatal("DATABASE_URL environment variable is required")
	}

	// 2. Connect to TimescaleDB
	// We use pgxpool for connection pooling and best performance with Timescale
	config, err := pgxpool.ParseConfig(dbURL)
	if err != nil {
		log.Fatal("Unable to parse DB URL:", err)
	}

	pool, err := pgxpool.NewWithConfig(context.Background(), config)
	if err != nil {
		log.Fatal("Unable to connect to database:", err)
	}
	defer pool.Close()

	// 3. Test Connection
	err = pool.Ping(context.Background())
	if err != nil {
		log.Fatal("Could not ping database:", err)
	}
	log.Println("✅ Successfully connected to TimescaleDB!")

	// 4. Start HTTP Server
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("LifeOS is healthy"))
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("🚀 Server starting on port %s", port)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatal(err)
	}
}